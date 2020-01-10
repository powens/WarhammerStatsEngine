import dash
import dash_daq as daq
import re
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

from .layout import GraphLayout, InputGenerator, MultiOptionGenerator

from .util import compute

from ..constants import TAB_COUNT


class CallbackMapper(object):
  def __init__(self, outputs=None, inputs=None, states=None):
    self._outputs = outputs or {}
    self._outputs_order = sorted(self._outputs.keys())
    self._inputs = inputs or {}
    self._inputs_order = sorted(self._inputs.keys())
    self._states = states or {}
    self._states_order = sorted(self._states.keys())

  @property
  def outputs(self):
    return [Output(k, self._outputs[k]) for k in self._outputs_order]

  @property
  def inputs(self):
    return [Input(k, self._inputs[k]) for k in self._inputs_order]

  @property
  def states(self):
    return [State(k, self._states[k]) for k in self._states_order]

  def input_to_kwargs_by_tab(self, args, tab_count):
    inputs = self.input_to_kwargs(args)
    tab_inputs = {i: {'inputs': {}, 'states': {}} for i in range(-1, tab_count)}
    for k in inputs['inputs']:
      match = re.match(r'(.*)_(\d+).*', k)
      if match:
        name, number = match.groups()
        tab_inputs[int(number)]['inputs'][name] = inputs['inputs'][k]
      else:
        tab_inputs[-1]['inputs'][k] = inputs['inputs'][k]
    for k in inputs['states']:
      match = re.match(r'(.*)_(\d+).*', k)
      if match:
        name, number = match.groups()
        tab_inputs[int(number)]['states'][name] = inputs['states'][k]
      else:
        tab_inputs[-1]['states'][k] = inputs['states'][k]
    return tab_inputs

  def input_to_kwargs(self, args):
    input_dict = {}
    state_dict = {}
    for i, key in enumerate(self._inputs_order):
      input_dict[key] = args[i]
    for j, key in enumerate(self._states_order):
      state_dict[key] = args[len(self._inputs_order) + j]
    return {'inputs': input_dict, 'states': state_dict}

  def dict_to_output(self, outputs):
    return [outputs[k] for k in self._outputs_order]


class CallbackController(object):
  def __init__(self, app, tab_count):
    self.app = app
    self.tab_count = tab_count
    self.graph_layout = GraphLayout()
    self.input_generator = InputGenerator()
    self.multi_generator = MultiOptionGenerator()

  def graph_inputs(self):
    inputs = self.input_generator.graph_inputs(self.tab_count)
    return [[x, 'checked' if 'enabled' in x else'value'] for x in inputs]

  def setup_callbacks(self):
    self.setup_graph_callbacks()
    self.setup_input_callbacks()

  def setup_graph_callbacks(self):
    mapper = CallbackMapper(
      outputs=self._graph_updates(),
      inputs=self.input_generator.graph_inputs(self.tab_count),
      states=self._graph_updates(),
    )
    @self.app.callback(mapper.outputs, mapper.inputs,mapper.states)
    def graph_callback(*args):
      tab_data = mapper.input_to_kwargs_by_tab(args, self.tab_count)
      result_dict = self.update_graph(tab_data)
      return mapper.dict_to_output(result_dict)

  def _graph_updates(self):
    return {
      **{'damage_graph': 'figure'},
      **{f'avg_display_{i}': 'children' for i in range(self.tab_count)},
      **{f'std_display_{i}': 'children' for i in range(self.tab_count)},
    }

  def setup_input_callbacks(self):
    for i in range(self.tab_count):
      self.setup_input_tab_callback(i)

  def setup_input_tab_callback(self, tab_index):
    self.disable_callback(tab_index)
    self.tab_name_callback(tab_index)
    self.shot_mods_callback(tab_index)
    self.hit_mods_callback(tab_index)
    self.wound_mods_callback(tab_index)
    self.save_mods_callback(tab_index)
    self.damage_mods_callback(tab_index)

  def disable_callback(self, tab_index):
    @self.app.callback(
      self._disable_outputs(tab_index),
      [Input('enabled_{}'.format(tab_index), 'checked')],
    )
    def disable_tab_options(enable):
        return [not enable] * 15

  def _disable_outputs(self, tab_index):
    ids = ['damage_mods_{}', 'save_mods_{}', 'wound_mods_{}', 'hit_mods_{}', 'shot_mods_{}',
           'ws_{}', 'toughness_{}', 'strength_{}', 'ap_{}', 'save_{}', 'invuln_{}', 'fnp_{}',
           'wounds_{}', 'shots_{}', 'damage_{}']
    return [Output(x.format(tab_index), 'disabled') for x in ids]


  def tab_name_callback(self, tab_index):
    @self.app.callback(
      Output('tab_{}'.format(tab_index), 'label'),
      [Input('tab_name_{}'.format(tab_index), 'value')],
    )
    def update_tab_name(value):
        return value if len(value) > 2 else 'Profile'


  def shot_mods_callback(self, tab_index):
    @self.app.callback(
      Output('shot_mods_{}'.format(tab_index), 'options'),
      [Input('shot_mods_{}'.format(tab_index), 'value')],
    )
    def update_shot_options(value):
      return self.multi_generator.shot_options(value or [])

  def hit_mods_callback(self, tab_index):
    @self.app.callback(
      Output('hit_mods_{}'.format(tab_index), 'options'),
      [Input('hit_mods_{}'.format(tab_index), 'value')],
    )
    def update_hit_options(value):
      return self.multi_generator.hit_options(value or [])

  def wound_mods_callback(self, tab_index):
    @self.app.callback(
      Output('wound_mods_{}'.format(tab_index), 'options'),
      [Input('wound_mods_{}'.format(tab_index), 'value')],
    )
    def update_wound_options(value):
      return self.multi_generator.wound_options(value or [])

  def save_mods_callback(self, tab_index):
    @self.app.callback(
      Output('save_mods_{}'.format(tab_index), 'options'),
      [Input('save_mods_{}'.format(tab_index), 'value')],
    )
    def update_save_options(value):
      return self.multi_generator.save_options(value or [])

  def damage_mods_callback(self, tab_index):
    @self.app.callback(
      Output('damage_mods_{}'.format(tab_index), 'options'),
      [Input('damage_mods_{}'.format(tab_index), 'value')],
    )
    def update_damage_options(value):
      return MultiOptionGenerator().damage_options(value or [])

  def update_graph(self, tab_data):
    graph_data = tab_data[-1]['states']['damage_graph']['data']
    output = {}
    if graph_data == [{}] * self.tab_count:
      changed_tabs = list(range(self.tab_count))
    else:
      changed_tabs = self.tabs_changed()
    for tab_number in range(self.tab_count):
      if tab_number in changed_tabs:
        data = compute(**tab_data[tab_number]['inputs'])
        graph_data[tab_number] = {
          'x': [i for i, x in enumerate(data['values'])],
          'y': [100*x for i, x in enumerate(data['values'])],
          'name': tab_data[tab_number]['inputs']['tab_name'],
        }
        output[f'avg_display_{tab_number}'] = 'Average: {}'.format(round(data['mean'], 2))
        output[f'std_display_{tab_number}'] = 'σ: {}'.format(round(data['std'], 2))
      else:
        existing_data = graph_data[tab_number]
        existing_data['name'] = tab_data[tab_number]['inputs']['tab_name']
        graph_data[tab_number] = existing_data
        output[f'avg_display_{tab_number}'] = tab_data[tab_number]['states']['avg_display']
        output[f'std_display_{tab_number}'] = tab_data[tab_number]['states']['std_display']
    max_len = max(max([len(x.get('x', [])) for x in graph_data]), 20)
    output['damage_graph'] = self.graph_layout.figure_template(graph_data, max_len)
    return output

  def tabs_changed(self):
    ctx = dash.callback_context
    if not ctx:
      return list(range(TAB_COUNT))
    tabs = []
    for trigger in ctx.triggered:
      match = re.match(r'.*_(\d+).*', trigger['prop_id'])
      if match and 'tab_name' not in trigger['prop_id']:
        tabs.append(int(match.groups()[0]))
    return list(set(tabs))