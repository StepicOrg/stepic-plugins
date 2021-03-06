import base64
import fnmatch
import io
import os
import signal
import socket
import tarfile
import threading
import time
import uuid

import structlog
import oslo_messaging as messaging

from oslo_config import cfg
from base64 import b64encode
from functools import wraps

from . import settings
from .base import QUIZZES_DIR, load_by_name
from .exceptions import FormatError, PluginError
from .executable_base import jail_code_wrapper
from .schema import RPCSerializer


logger = structlog.get_logger()


class LoggedEndpointMetaclass(type):
    def __new__(mcs, name, bases, dct):
        def init(self, timeout_killer=None):
            self.timeout_killer = timeout_killer

        dct['__init__'] = init
        for name, method in dct.items():
            if not name.startswith('_') and callable(method):
                dct[name] = mcs.log_method_wrapper(method)
        return super().__new__(mcs, name, bases, dct)

    @classmethod
    def log_method_wrapper(mcs, method):
        def compact(value):
            if isinstance(value, (tuple, list)):
                return type(value)([compact(v) for v in value])
            elif isinstance(value, dict):
                return {k: compact(v) for k, v in value.items()}
            elif isinstance(value, str):
                return value if len(value) < 100 else value[:100] + '...'
            return value

        @wraps(method)
        @messaging.expected_exceptions(PluginError)
        def wrapper(self, *args, **kwargs):
            call_id = str(uuid.uuid4())[:8]
            log = logger.bind(method=method.__name__, args=compact(args), kwargs=compact(kwargs),
                              call_id=call_id, version=self.target.version)
            if self.target.namespace:
                log = log.bind(namespace=self.target.namespace)
            log.info("RPC method call started")
            start_time = time.time()
            if self.timeout_killer:
                self.timeout_killer.start_countdown()
            try:
                result = method(self, *args, **kwargs)
                log.debug("RPC method call result", result=result)
                return result
            except PluginError:
                raise
            except Exception as e:
                log.exception("Unexpected exception in plugin")
                raise PluginError("RPC method failed badly ({}): {}"
                                  .format(e.__class__.__name__, e))
            finally:
                if self.timeout_killer:
                    self.timeout_killer.reset_countdown()
                duration = int((time.time() - start_time) * 1000) / 1000
                log.info("RPC method call finished", duration=duration)

        return wrapper


class TimeoutKillerThread(threading.Thread):
    """A thread to kill the RPC server process and its children on timeout."""

    def __init__(self, timeout=300):
        super(TimeoutKillerThread, self).__init__()
        self.timeout = timeout
        self._is_active = True
        self._is_countdown_on = False

    def start_countdown(self):
        self._is_countdown_on = True

    def reset_countdown(self):
        self._is_countdown_on = False

    def stop(self):
        self._is_active = False

    def run(self):
        logger.info("Starting RPC timeout killer thread...")
        while self._is_active:
            if not self._is_countdown_on:
                time.sleep(1)
                continue
            start = time.time()
            while time.time() - start < self.timeout:
                if not self._is_active or not self._is_countdown_on:
                    break
                time.sleep(0.25)
            else:
                pgid = os.getpgid(os.getpid())
                logger.warning("Killing RPC server process group (%s), ran "
                               "too long: %.1fs", pgid, time.time() - start)
                os.killpg(pgid, signal.SIGKILL)
        logger.info("RPC timeout killer thread stopped")


class QuizEndpoint(metaclass=LoggedEndpointMetaclass):
    target = messaging.Target(namespace='quiz', version='0.2')

    def _quiz_instance(self, ctxt):
        quiz_class = load_by_name(ctxt['name'])
        return quiz_class(ctxt['source'],
                          supplementary=ctxt.get('supplementary'))

    def ping(self, ctxt, msg):
        return msg

    def validate_source(self, ctxt):
        self._quiz_instance(ctxt)

    def async_init(self, ctxt):
        return self._quiz_instance(ctxt).async_init()

    def generate(self, ctxt):
        return self._quiz_instance(ctxt).generate()

    def clean_reply(self, ctxt, reply, dataset):
        return self._quiz_instance(ctxt).clean_reply(reply, dataset=dataset)

    def check(self, ctxt, reply, clue):
        return self._quiz_instance(ctxt).check(reply, clue=clue)

    def cleanup(self, ctxt, clue):
        return self._quiz_instance(ctxt).cleanup(clue=clue)

    def list_computationally_hard_quizzes(self, ctxt):
        return settings.COMPUTATIONALLY_HARD_QUIZZES

    def _collect_quiz_static(self, quiz_directory, tarball):
        log = logger.bind()
        log.info("Start to collect static from quiz directory",
                 quiz_directory=quiz_directory)
        quiz_basedir = os.path.basename(quiz_directory)
        tarball_quiz_dir = os.path.join('stepic_plugins', quiz_basedir)

        coffee_pattern = '*.coffee'
        patterns = ['*.js', '*.css', '*.hbs', coffee_pattern]

        for file in os.listdir(quiz_directory):
            if all(not fnmatch.fnmatch(file, p) for p in patterns):
                continue
            source_file = os.path.join(quiz_directory, file)
            tar_file = os.path.join(tarball_quiz_dir, file)
            if fnmatch.fnmatch(file, coffee_pattern):
                log = log.bind(file=source_file)
                try:
                    import coffeescript
                except ImportError:
                    log.error("Package 'CoffeeScript' is required to compile "
                              "static file, it will be skipped")
                    continue

                tar_file = os.path.splitext(tar_file)[0] + '.js'
                try:
                    source_compiled = (coffeescript.compile_file(source_file)
                                       .encode())
                except (coffeescript.EngineError,
                        coffeescript.CompilationError):
                    log.exception("Failed to compile coffeescript file, "
                                  "it will be skipped")
                    continue
                log.info("Successfully compiled coffeescript file")
                tar_info = tarfile.TarInfo(name=tar_file)
                tar_info.size = len(source_compiled)
                tar_info.mtime = os.path.getmtime(source_file)
                tarball.addfile(tar_info, fileobj=io.BytesIO(source_compiled))
            else:
                tarball.add(source_file, arcname=tar_file)

    def get_static(self, ctxt):
        """Get static files for all quizzes bundled in a tarball.

        Coffeescript files are dynamically compiled before being added
        to a resulting tarball.

        :return: A Base64-encoded tarball file

        """
        tarball_fileobj = io.BytesIO()
        with tarfile.open(fileobj=tarball_fileobj, mode='w:gz') as tarball:
            for directory in os.listdir(QUIZZES_DIR):
                quiz_directory = os.path.join(QUIZZES_DIR, directory)
                if os.path.isdir(quiz_directory):
                    self._collect_quiz_static(quiz_directory, tarball)
        return base64.b64encode(tarball_fileobj.getvalue()).decode()

    def call(self, ctxt, name, args, kwargs):
        attr = getattr(self._quiz_instance(ctxt), name)
        if callable(attr):
            args = args or ()
            kwargs = kwargs or {}
            return attr(*args, **kwargs)
        return attr


class CodeJailEndpoint(metaclass=LoggedEndpointMetaclass):
    target = messaging.Target(namespace='codejail', version='0.1')

    def run_code(self, ctxt, command, code, files, argv, stdin):
        result = jail_code_wrapper(
            command, code=code, files=files, argv=argv, stdin=stdin)
        serializable_result = {
            'status': result.status,
            'stdout': b64encode(result.stdout).decode(),
            'stderr': b64encode(result.stderr).decode(),
            'time_limit_exceeded': result.time_limit_exceeded,
        }
        return serializable_result


_fake_transport = messaging.get_transport(cfg.CONF, 'fake:')
_fake_server = None


def get_server(transport_url, fake=False, timeout_killer=None):
    if not fake:
        transport = messaging.get_transport(cfg.CONF, transport_url)
        server_name = socket.gethostname()
    else:
        transport = _fake_transport
        server_name = 'fake_server'
    target = messaging.Target(topic='plugins', server=server_name)
    # noinspection PyArgumentList
    endpoints = [
        QuizEndpoint(timeout_killer=timeout_killer),
        CodeJailEndpoint(timeout_killer=timeout_killer),
    ]
    return messaging.get_rpc_server(transport, target, endpoints,
                                    executor='threading',
                                    serializer=RPCSerializer())


def start_fake_server():
    global _fake_server
    if _fake_server:
        return _fake_server
    _fake_server = get_server(None, fake=True)
    logger.info("Starting fake RPC server in thread")
    threading.Thread(target=_fake_server.start, daemon=True).start()
    return _fake_server
