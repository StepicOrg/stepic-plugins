App.MatchingQuizComponent = Em.Component.extend
  setInitial: (->
    if not @get('reply.ordering')
      N = @get('dataset.pairs.length')
      initial_ordering = Array.apply(null, {length: N}).map(Number.call, Number) #  0, 1, 2, 3, ...
      @set 'reply',
        ordering: initial_ordering
    @set 'options', ({index: index, second: @get('dataset.pairs')[index].second} for index in @get('reply.ordering'))
  ).on('init')

  onOptionsChanged: (->
    @set 'reply',  ordering: (option.index for option in @get('options'))
  ).observes('options')

  setBindings: (->
    dragSource = null
    component = @
    options = @$('.matching-quiz__second-item')
    options.off()
    .on 'dragstart', (e)->
      dragSource = @
      $(@).addClass 'matching-quiz__second-item-extracted'
      e.originalEvent.dataTransfer.setData 'text/html', @outerHTML
    .on 'dragover', (e)->
      options.removeClass('matching-quiz__second-item-insert-before').removeClass 'matching-quiz__second-item-insert-after'
      if options.index(dragSource) > options.index(@)
        $(@).addClass 'matching-quiz__second-item-insert-before'
      else
        $(@).addClass 'matching-quiz__second-item-insert-after'
      e.preventDefault()
    .on 'dragend', (e) ->
      options.removeClass('matching-quiz__second-item-insert-before').removeClass('matching-quiz__second-item-insert-after').removeClass 'matching-quiz__second-item-extracted'
    .on 'dragleave', (e) ->
      options.removeClass('matching-quiz__second-item-insert-before').removeClass 'matching-quiz__second-item-insert-after'
    .on 'drop', (e)->
      component.moveRow options.index(dragSource), options.index(@) - options.index(dragSource)
  ).on('didInsertElement')

  moveItem: (list, position, shift)->
    while (shift != 0)
      delta = shift / Math.abs(shift)
      row = list[position]
      list[position] = list[position + delta]
      list[position + delta] = row
      position = position + delta
      shift = shift - delta
    list

  moveRow: (position, shift)->
    new_options = @get('options').slice()
    new_options = @moveItem new_options, position, shift
    @set 'options', new_options
    Em.run.next =>
      @setBindings()
      element = @$('.matching-quiz__second-items')[0]
      if MathJax? and element
        MathJax.Hub.Queue(["Typeset", MathJax.Hub, element])

  actions:
    moveIt: (row, shift)->
      new_options = @get('options').slice()
      pos = new_options.indexOf(row)
      @moveRow pos, shift