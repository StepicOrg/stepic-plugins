Plugin API
**********

This document demonstrates plugin API with the example of simple-choice quiz.
It should be read alongside with plugin source at `quizzes/simple_choice`_.


Quiz Design
===========

Author specifies a list of options, one of which is correct and all others are wrong.

Student is presented with a shuffled list of options. He should pick the correct one.

This design can be extended in a numerous ways, but for the sake of simplicity
we won't do this. Full featured implementation of a choice quiz can be found at
`quizzes/choice`.

Directory Structure
===================

Directory `quizzes/simple_choice` consists of the following files:
    * `__init__.py`_ -- server part of the quiz is defined here.
    * `tests.py`_ -- server part tests.
    * `edit.js`_, `edit.hbs`_ -- this pair of files describes edit interface for teacher.
    * `show.js`_, `show.hbs`_ -- this pair of files describes interface for student.
    * `style.css` -- css styles for frontend.


Server side
==========

Server side is written in Python3 and consists of one file -- `__init__.py`_.
In this file `SimpleChoiceQuiz` class is defined. It inherits from `BaseQuiz`
and implements several abstract members.


**name** is quiz type in dasherized-case.


**Schemas** is a specification of a communication format between python backend and javascript frontend.
It describes three types of objects.

*Source* is the data needed to create quiz instance. It is created and rendered in `edit.js`_.

*Dataset* is presented to the student for solving. It is created in `__init__.py`_ and
rendered in `show.js`_.

*Reply* is the student's solution to the dataset. It is created and rendered in `show.js`_

This object's types are expressed with the help of JSON specification mini language.
In this language, objects types are specified as python dictionaries,
JSON arrays as lists and primitive types like ``int``, ``str``, etc.

For example, an object with field ``numbers`` which is an array of ints is specified as::

    {
        'numbers': [int]
    }

Source of `simple_choice` quiz can be specified as a list of text options with correctness marks::

    {
        'options': [{'is_correct': bool, 'text': str}]
    }

Dataset should be a list of strings::

    {
        'options': [str]
    }

Reply should be a list of booleans::

    {
        'choices': [bool]
    }


**__init__(self, source)** instantiates quiz from source.

**generate(self)** generates a (dataset, clue) pair. clue is used to check user's response.

**clean_reply(self, reply, dataset)** validates and transforms user's reply.

**check(self, reply, clue)** checks valid and transformed reply.

Tests for backend can be found in `tests.py`_. Note the use of `SimpleChoiceQuiz.{Source, Dataset, Reply}`
to transform raw dictionaries into parsed objects.

Client Side
===========

Client side is written in javascript, Handlebars and css. It defines two functions
``editSimpleChoiceQuiz`` and ``showSimpleChoiceQuiz``. This functions create necessary UI and
return an object with ``submit`` method. This method should return an object representing quiz source
for ``editSimpleChoiceQuiz`` and reply for ``showSimpleChoiceQuiz``.

``editSimpleChoiceQuiz`` function takes three arguments:
    * ``target`` -- jQuery object representing parent DOM element.
    * ``template`` -- a compiled handlebars template.
    * ``source`` -- null, if it is a new quiz, or existing quiz source.

``showSimpleChoiceQuiz`` function takes five arguments:
    * ``target``, ``template`` -- same as edit.
    * ``dataset`` -- dataset, conforming to `SimpleChoiceQuiz.Schemas.dataset`
    * ``reply`` -- an existing reply(`SimpleChoiceQuiz.Schemas.reply`) or a null.
    * ``disabled`` -- a boolean flag. If it is on, UI should be rendered in disabled state.


Launching The Quiz
==================

To check the quiz, start development server first::
  $ python3 dev-server/server.py simple-choice

And then open 127.0.0.1:5000 in your browser.


Advanced Plugins
================

Plugin can specify `async_init` method. It is used for time consuming initialization and checking.

Fork of [CodeJail](https://github.com/bioinf/codejail) is used for untrusted code execution.

It's possible to use CoffeeScript to create frontend.

Ember components can be used to create frontend.

Check existing quizzes for examples of this features.

.. _\__init__.py: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/__init__.py
.. _tests.py: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/tests.py
.. _edit.js: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/edit.js
.. _edit.hbs: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/edit.hbs
.. _show.js: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/show.js
.. _show.hbs: https://github.com/StepicOrg/stepic-plugins/blob/master/stepic_plugins/quizzes/simple_choice/show.hbs
.. _quizzes/simple_choice: https://github.com/StepicOrg/stepic-plugins/tree/master/stepic_plugins/quizzes/simple_choice
