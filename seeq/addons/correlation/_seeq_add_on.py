from IPython.display import HTML, display, clear_output, Javascript
import ipyvuetify as v
import pandas as pd
import numpy as np
import datetime
import re
import math
import json
import pickle
import warnings
import plotly.graph_objects as go
from seeq import spy
from .utils import get_worksheet_url, pull_only_signals, get_workbook_worksheet_workstep_ids, create_condition
from seeq.addons.correlation._config import _user_guide, _github_issues
from . import default_preprocessing_wrapper
from . import _heatmap_plot, lags_coeffs, worksheet_with_lagged_signals, worksheet_corrs_and_time_shifts

warnings.filterwarnings('ignore')


class CorrelationHeatmap:
    """
    This is the main class for the User Interface of the Correlation Add-on.
    To create an instance, either a Seeq Data Lab project URL with appropriate
    query parameters or pd.DataFrame must be passed. If a pd.DataFrame is
    passed, the functionality to push data back to the Seeq server is disabled.

    """
    colors = {
        'app_bar': '#007960',
        'controls_background': '#F6F6F6',
        'visualization_background': '#FFFFFF',
        'seeq_primary': '#007960',
        'slider_selected': '#007960',
        'slider_track_unselected': '#BDBDBD'
    }

    heatmap_item_size = 60

    additional_styles = """
        <style>
        #appmode-leave {display: none;}
        .background_box { background-color:#007960 !important; } 
        .js-plotly-plot .plotly .modebar-btn[data-title="Produced with Plotly"] {display: none;}
        .vuetify-styles .theme--light.v-list-item .v-list-item__action-text, 
        .vuetify-styles .theme--light.v-list-item .v-list-item__subtitle {color: #212529;}
        .vuetify-styles .theme--light.v-list-item:not(.v-list-item--active):not(.v-list-item--disabled) 
        {color: #007960 !important;}
        .vuetify-styles .v-label {font-size: 14px;}
        .vuetify-styles .v-application {font-family: "Source Sans Pro","Helvetica Neue",Helvetica,Arial,sans-serif;}
        .v-snack {position: absolute !important;top: -470px;right: 0 !important; left: unset !important;}
        </style>"""
    v.theme.themes.light.success = '#007960'
    v.theme.themes.light.primary = '#007960'
    no_data_message = 'No data available'

    def __init__(self, sdl_notebook_url=None, df=None, datasource=None, seeq_url=None):
        display(HTML("<style>#appmode-leave {display: none;}"))
        if sdl_notebook_url is None and not isinstance(df, pd.DataFrame):
            raise ValueError('Need either the SDL url or a pd.DataFrame with the signals to analyze')
        if sdl_notebook_url is None and isinstance(df, pd.DataFrame):
            self.df = df
            self.worksheet_id = None
            self.worksheet_id = None
            self.info_message = "The current signals are not associated to an Analysis worksheet. Cannot export " \
                                "shifted signals to Analysis worksheet"
            self.info_style = "color: #ff5252 !important;"
            self.export_disabled = True
        if sdl_notebook_url is not None:
            self.workbook_id, self.worksheet_id, self.workstep_id = get_workbook_worksheet_workstep_ids(
                sdl_notebook_url)
            self.worksheet_url = get_worksheet_url(sdl_notebook_url)
            self.df = pull_only_signals(self.worksheet_url)
            self.worksheet = spy.utils.get_analysis_worksheet_from_url(self.worksheet_url)
            clear_output()
            self.info_message = ''
            self.info_style = ''
            self.export_disabled = False

        self.datasource = datasource
        self.seeq_url = seeq_url
        self.time_output_unit = 'auto'
        self.max_time_str = 'auto'
        self.max_time_str_error = ''
        self.coeffs_df = pd.DataFrame()
        self.time_shifts_df = pd.DataFrame()
        self.table_displayed = pd.DataFrame()
        self.time_shift_min = 0
        self.time_shift_max = 0
        self.time_unit = ''
        self.time_unit_display = []
        self.actual_max_time_shift = None

        self.signals_dict = None
        self.signal_ids = None
        self.signal_names = None
        self.time_shifts = None
        self.start_time = None
        self.end_time = None
        self.signal_pairs_ids = []

        if self.df.empty:
            self.df_processed = pd.DataFrame()
        else:
            # We don't want to remove outliers here. Increased the outlier_sensitivity
            self.df_processed = default_preprocessing_wrapper(self.df, consecutivenans=0.04, percent_nan=0.0,
                                                              bypass_processing=False)
        self.current_df = self.df_processed.copy()
        self.current_signals = list(self.current_df.columns)
        self.coeffs_time_shifts_calc(self.max_time_str, self.time_output_unit)
        correlation_fig = _heatmap_plot(pickle.dumps(self.coeffs_df), pickle.dumps(self.time_shifts_df),
                                        time_unit=self.time_unit, lags_plot=False)

        self.graph = go.FigureWidget()
        self.create_displayed_fig(correlation_fig)

        # App layout
        self.hamburger_menu = HamburgerMenu()
        self.app = v.App(v_model=None, id='correlation-analysis-app')
        self.appBar = v.AppBar(
            color=self.colors['app_bar'],
            dense=True,
            dark=True,
            children=[v.ToolbarTitle(children=['Correlation Analysis']),
                      v.Spacer(),
                      v.Divider(vertical=True),
                      self.hamburger_menu])

        # Time shifts switch
        self.time_shifts_switch = v.Switch(id='time-shift-switch', v_model=True,
                                           label="", persistent_hint=False, color='#007960', flat=False,
                                           inset=True, v_on='tooltip.on',
                                           class_='mt-1 ml-1')

        self.time_shift_switch_tooltip = v.Tooltip(top=True, v_slots=[{
            'name': 'activator',
            'variable': 'tooltip',
            'children': self.time_shifts_switch
        }], children=['Turn time shifts OFF/ON'])

        # Max. time shift input
        self.max_time_shifts, self.max_time_shifts_tooltip = create_input_param_box(
            v_model=self.max_time_str, label="Max. Shift", color=self.colors['seeq_primary'],
            style_='max-width: 80px; font-size: small; text-align-last: end;', class_='ml-2',
            tooltip='Enter "auto" to auto-calculate max. time shift, or enter time with units (e.g. 1h, 2min)')

        # Time shifts container
        self.time_shifts_container = v.Html(tag='div', class_='d-flex flex-wrap',
                                            children=[self.time_shift_switch_tooltip, self.max_time_shifts_tooltip])

        self.time_shift_controls_container = v.Html(tag='div', class_='d-flex flex-column pt-5 pr-3',
                                                    # style_='margin-top: 30px',
                                                    children=[
                                                        v.Html(tag='h4', children=['Time Shifts'],
                                                               class_='mb-4'),
                                                        self.time_shifts_container])

        # Coefficients and time shifts controls
        coeffs_times_shifts_btns = [
            dict(name='Coefficients', v_model='', style_='text-transform: capitalize; min-width: 100px',
                 tooltip='Shows the cross-correlation coefficients among signals'),
            dict(name='Time Shifts', v_model='', style_='text-transform: capitalize; min-width: 100px',
                 tooltip='Shows the time shifts of signals to maximize cross correlations')
        ]

        self.output_values_toggle = ToggleButtons(coeffs_times_shifts_btns, v_model=0, mandatory=True, tile=True,
                                                  color=self.colors['seeq_primary'],
                                                  borderless=False, dense=True, class_='flex-wrap',
                                                  style_='background: transparent;')

        self.coeff_times_container = v.Html(tag='div', class_='d-flex flex-column pt-5 pr-3',
                                            children=[v.Html(tag='h4', children=['Output Values'], class_='mb-4'),
                                                      self.output_values_toggle])

        # Plot and table toggle buttons
        plot_table_btns = [
            dict(name='Plot', v_model='', style_='text-transform: capitalize; min-width: 55px',
                 tooltip='Display values as a heatmap plot'),
            dict(name='Table', v_model='', style_='text-transform: capitalize; min-width: 55px',
                 tooltip='Display values in a table')
        ]

        self.output_type_toggle = ToggleButtons(plot_table_btns, v_model=0, mandatory=True, tile=True,
                                                color=self.colors['seeq_primary'], borderless=False, dense=True,
                                                style_='background: transparent;', class_='flex-wrap',
                                                )

        self.plot_table_container = v.Html(tag='div', class_='d-flex flex-column pt-5 pr-3',
                                           children=[v.Html(tag='h4', children=['Output Type'], class_='mb-4'),
                                                     self.output_type_toggle])

        # Filters
        self.coeff_lower_bound = self.bound_box(v_model=-1.0, color=self.colors['seeq_primary'])
        self.coeff_upper_bound = self.bound_box(v_model=1.0, color=self.colors['seeq_primary'])
        self.coeff_slider, self.coeff_slider_tooltip = self.slider_widget(color=self.colors['slider_selected'],
                                                                          track_color=self.colors[
                                                                              'slider_track_unselected'],
                                                                          thumb_color=self.colors['slider_selected'],
                                                                          min_=-1.0, max_=1.0, step=0.01,
                                                                          v_model=(-1.0, 1.0),
                                                                          tooltip='Select the range of coefficient '
                                                                                  'values to display')

        self.time_lower_bound = self.bound_box(v_model=np.round(self.time_shift_min, 1),
                                               color=self.colors['seeq_primary'])

        self.time_upper_bound = self.bound_box(v_model=np.round(self.time_shift_max, 1),
                                               color=self.colors['seeq_primary'])
        self.time_slider, self.time_slider_tooltip = self.slider_widget(color=self.colors['slider_selected'],
                                                                        track_color=self.colors[
                                                                            'slider_track_unselected'],
                                                                        thumb_color=self.colors['slider_selected'],
                                                                        min_=self.time_shift_min,
                                                                        max_=self.time_shift_max, step=0.1,
                                                                        v_model=(
                                                                            self.time_shift_min, self.time_shift_max),
                                                                        tooltip='Select the range of time shift '
                                                                                'values to display')

        # create the checkboxes
        self.coeff_range_checkbox, self.coeff_range_checkbox_tooltip = create_checkbox(
            label='Outer range',
            color=self.colors['seeq_primary'],
            dense=True,
            class_=' ml-4', v_model=False,
            tooltip='Select the outer range instead of the inner range')

        self.time_range_checkbox, self.time_range_checkbox_tooltip = create_checkbox(
            label='Outer range',
            color=self.colors['seeq_primary'],
            dense=True,
            class_=' ml-4 ',
            v_model=False,
            tooltip='Select the outer range instead of the inner range')

        self.coeff_filter = v.Html(tag='div', class_='d-flex align-center flex-wrap',
                                   children=[v.Subheader(children=['Coefficients'], class_='pa-0'),
                                             v.Html(tag='div', class_='d-flex pl-3 align-center',
                                                    children=[self.coeff_lower_bound,
                                                              self.coeff_slider_tooltip,
                                                              self.coeff_upper_bound]),
                                             self.coeff_range_checkbox_tooltip
                                             ])

        self.time_shift_subheader = v.Subheader(children=self.time_unit_display, class_='pa-0')

        self.time_shifts_filter = v.Html(tag='div', class_='d-flex align-center flex-wrap',
                                         children=[self.time_shift_subheader,
                                                   v.Html(tag='div', class_='d-flex pl-4 align-center',
                                                          children=[self.time_lower_bound,
                                                                    self.time_slider_tooltip,
                                                                    self.time_upper_bound]),
                                                   self.time_range_checkbox_tooltip
                                                   ])

        self.filters = v.Html(tag='div', class_='d-flex flex-column',
                              children=[self.coeff_filter, self.time_shifts_filter])

        self.filters_container = v.Html(tag='div', class_='d-flex flex-column pt-5 pr-3',
                                        children=[v.Html(tag='h4', children=['Filters'], class_='mb-1'),
                                                  self.filters])

        # Save to workbench button
        self.dialog_button = v.Btn(color='success', children=['Create Signals'],  # v_on='x.on',
                                   class_='align-self-center', style_='text-transform: capitalize;')
        self.button_box = v.Html(tag='div', class_='d-flex flex-center pb-3', children=[self.dialog_button])

        self.save_dialog = CreateSignalsMenu(self, max_width='700px', v_model=False)

        # snackbar
        self.close_snackbar = v.Btn(color='white', icon=True, children=[v.Icon(children=['mdi-window-close'])])
        self.signals_created = v.Snackbar(v_model=False, app=True, color='success', shaped=True,
                                          children=['Shifted signals have been created in Workbench',
                                                    self.close_snackbar])

        # controls bar
        self.controls = v.Html(tag='div', class_='d-flex flex-row flex-wrap justify-space-between pr-3 pl-3',
                               style_=f"background-color: {self.colors['controls_background']}; opacity: 1",
                               children=[self.time_shift_controls_container, self.coeff_times_container,
                                         self.plot_table_container, self.filters_container, self.button_box,
                                         self.save_dialog, self.signals_created])

        # Visualization container
        self.visualization = v.Html(tag='div', id='plotly-heatmap',
                                    # class_='d-flex flex-row justify-center align-center',
                                    style_=f"background-color: {self.colors['visualization_background']};"
                                           f"border:2px solid {self.colors['controls_background']};",
                                    children=[self.graph])

        self.progress = v.Html(tag='div', style_=f"height: 200px;",
                               class_='d-flex flex-row justify-center align-center',
                               children=[v.ProgressCircular(color=self.colors['seeq_primary'],
                                                            size='50',
                                                            width='6',
                                                            indeterminate=True)])

    @staticmethod
    def bound_box(v_model, color):
        return v.TextField(v_model=v_model,
                           hide_details="auto",
                           dense=True,
                           height='20px',
                           style_='max-width: 50px; min-width: 40px; font-size: smaller; text-align-last: auto;',
                           outlined=True,
                           shaped=False,
                           filled=False,
                           color=color,
                           counter=False,
                           )

    @staticmethod
    def slider_widget(color, track_color, thumb_color, min_, max_, step, v_model: tuple, label='', tooltip=''):
        slider = v.RangeSlider(model='range', color=color, track_color=track_color, thumb_color=thumb_color,
                               dense=True,
                               thumb_label=True, min=min_, max=max_, label=label, step=step, v_model=v_model,
                               height='1px', loader_height='1px', v_on='tooltip.on', class_='align-self-end',
                               style_='min-width: 80px;'
                               )
        slider_tooltip = v.Tooltip(bottom=True, v_slots=[{
            'name': 'activator',
            'variable': 'tooltip',
            'children': slider
        }], children=[tooltip])
        return slider, slider_tooltip

    def coeffs_time_shifts_calc(self, max_time_shift, time_output_unit):
        if self.current_df.empty:
            return
        lags, coeffs, sampling_time, time_unit, maxlags = lags_coeffs(self.current_df, max_time_shift, time_output_unit)
        time_shifts = lags * sampling_time
        self.actual_max_time_shift = None if max_time_shift is None else f"{maxlags * sampling_time} {time_unit}"
        self.time_unit = time_unit
        self.time_unit_display = [f'Time Shifts', v.Html(tag='br'), f'({self.time_unit})']

        self.coeffs_df = pd.DataFrame(data=coeffs, columns=self.current_df.columns,
                                      index=self.current_df.columns)
        self.time_shifts_df = pd.DataFrame(data=time_shifts, columns=self.current_df.columns,
                                           index=self.current_df.columns)

        if time_shifts.min() == 0 and time_shifts.max() == 0:
            self.time_shift_min = -0.0001
            self.time_shift_max = 0.0001
        else:
            self.time_shift_min = round_down(time_shifts.min(), 1)
            self.time_shift_max = round_up(time_shifts.max(), 1)

        if hasattr(self, 'time_slider'):
            self.time_slider.min = self.time_shift_min
            self.time_slider.max = self.time_shift_max
            new_min_slider = self.time_slider.v_model[0]
            new_max_slider = self.time_slider.v_model[1]

            if self.time_slider.v_model[0] < self.time_shift_min or self.time_lower_bound.v_model == 0:
                if self.time_shift_min == -0.0001:
                    new_min_slider = 0
                else:
                    new_min_slider = self.time_shift_min
            if self.time_slider.v_model[1] > self.time_shift_max or self.time_upper_bound.v_model == 0:
                if self.time_shift_max == 0.0001:
                    new_max_slider = 0
                else:
                    new_max_slider = self.time_shift_max

            self.time_slider.v_model = (new_min_slider, new_max_slider)
            self.time_lower_bound.v_model = new_min_slider
            self.time_upper_bound.v_model = new_max_slider
            self.time_shift_subheader.children = self.time_unit_display

    def validate_units_(self):
        self.max_time_str = self.max_time_shifts.v_model
        self.max_time_shifts.v_model, self.max_time_str_error, self.time_output_unit = validate_units(
            self.max_time_shifts.v_model, self.time_shifts_switch.v_model)

    def resize_plot(self):
        min_size = len(self.coeffs_df) * self.heatmap_item_size
        if min_size <= 300:  # it looks like plotly defaults to 300 px for the size of the plot
            return
        else:
            self.graph.layout.height = min_size

    def create_displayed_fig(self, heatmap_fig):
        # First, clear previous plots
        self.graph = go.FigureWidget()
        self.graph.data = []
        if len(heatmap_fig.data) == 0:
            self.graph = self.no_data_message
            return
        self.graph.add_trace(heatmap_fig.data[0])
        self.graph.layout = heatmap_fig.layout
        self.resize_plot()

    def table_widget(self, df, time_shift_plot):
        if df.empty:
            return self.no_data_message
        if time_shift_plot:
            self.table_displayed = df.reset_index().rename(columns={'index': 'Name'})
            self.table_displayed.columns = [f"{x}\n({self.time_unit})" if x != 'Name' else x for x in
                                            self.table_displayed.columns]

        else:
            self.table_displayed = df.reset_index().rename(columns={'index': 'Name'})

        headers = [{
            "text": col,
            "value": col,
        } for col in self.table_displayed.columns]
        headers[0].update({'align': 'center', 'divider': True, 'sortable': True})
        items = json.loads(self.table_displayed.round(2).to_json(orient='records'))
        return v.DataTable(items=items, headers=headers, hide_default_header=False, hide_default_footer=True,
                           dense=False, disable_pagination=False, disable_sort=True, items_per_page=500)

    def get_boolean_df(self):
        if self.coeff_range_checkbox.v_model:
            boolean_coeffs = ((self.coeffs_df.round(2) >= self.coeff_slider.min) &
                              (self.coeffs_df.round(2) <= self.coeff_slider.v_model[0])) | \
                             ((self.coeffs_df.round(2) >= self.coeff_slider.v_model[1]) &
                              (self.coeffs_df.round(2) <= self.coeff_slider.max))
        else:
            boolean_coeffs = ((self.coeffs_df.round(2) >= self.coeff_slider.v_model[0]) &
                              (self.coeffs_df.round(2) <= self.coeff_slider.v_model[1]))

        if self.time_range_checkbox.v_model:
            boolean_time_shifts = ((self.time_shifts_df.round(1) >= self.time_slider.min) &
                                   (self.time_shifts_df.round(1) <= self.time_slider.v_model[0])) | \
                                  ((self.time_shifts_df.round(1) >= self.time_slider.v_model[1]) &
                                   (self.time_shifts_df.round(1) <= self.time_slider.max))
        else:
            boolean_time_shifts = ((self.time_shifts_df.round(1) >= self.time_slider.v_model[0]) &
                                   (self.time_shifts_df.round(1) <= self.time_slider.v_model[1]))
        boolean_df = boolean_coeffs & boolean_time_shifts  # type: pd.DataFrame
        return boolean_df

    def update_display(self):
        # get output_values
        boolean_df = self.get_boolean_df()  # type: pd.DataFrame
        # noinspection PyArgumentList
        self.current_signals = list(
            set(
                list(boolean_df.columns[boolean_df.any(axis='columns')]) +
                list(boolean_df.columns[boolean_df.any(axis='index')])
            )
        )
        self.save_dialog.target_dropdown.items = self.current_signals

        if self.output_values_toggle.v_model == 0:
            time_shift_plot = False
            table_df = self.coeffs_df.loc[self.current_signals][self.current_signals]
            primary_df = self.coeffs_df
            secondary_df = self.time_shifts_df

        elif self.output_values_toggle.v_model == 1:
            time_shift_plot = True
            table_df = self.time_shifts_df.loc[self.current_signals][self.current_signals]
            primary_df = self.time_shifts_df
            secondary_df = self.coeffs_df

        else:
            time_shift_plot = None
            table_df = None
            primary_df = None
            secondary_df = None

        if self.output_type_toggle.v_model == 0:
            # get the new plot
            heatmap_fig = _heatmap_plot(pickle.dumps(primary_df), pickle.dumps(secondary_df),
                                        time_unit=self.time_unit, lags_plot=time_shift_plot, boolean_df=boolean_df)
            self.create_displayed_fig(heatmap_fig)
            self.visualization.children = [self.graph]
        if self.output_type_toggle.v_model == 1:
            # let's try to keep the same signal order as in the heatmap
            signals_ordered = [x for x in primary_df.columns if x in table_df.columns]
            self.visualization.children = [
                self.table_widget(table_df[signals_ordered].reindex(signals_ordered), time_shift_plot)]

    def recalculate_coeffs_and_time_shifts(self):
        self.validate_units_()
        self.max_time_shifts.error_messages = self.max_time_str_error
        if self.max_time_str_error != '':
            self.max_time_shifts.error = True
            return
        self.max_time_shifts.error = False
        self.coeffs_time_shifts_calc(self.max_time_str, self.time_output_unit)

    def time_shifts_switch_events(self, *_):
        if self.time_shifts_switch.v_model:
            self.max_time_shifts.disabled = False
            self.max_time_shifts.style_ = self.max_time_shifts.style_.replace('display: none;', '')
            if self.max_time_shifts.v_model is None or self.max_time_shifts.v_model == '':
                self.max_time_shifts.v_model = 'auto'
        else:
            self.max_time_shifts.style_ = self.max_time_shifts.style_ + 'display: none;'
            self.max_time_shifts.disabled = True
            self.max_time_shifts.v_model = None

        self.visualization.children = [self.progress]
        self.recalculate_coeffs_and_time_shifts()
        self.update_display()

    def max_shifts_events(self, *_):
        if self.max_time_str == self.max_time_shifts.v_model:
            return
        self.visualization.children = [self.progress]
        self.recalculate_coeffs_and_time_shifts()
        if self.max_time_shifts.error:
            return
        self.update_display()

    def slider_colors(self, checkbox_name, slider_name):
        checkbox = getattr(self, checkbox_name)
        slider = getattr(self, slider_name)
        if checkbox.v_model:
            slider.color = self.colors['slider_track_unselected']
            slider.track_color = self.colors['slider_selected']
        else:
            slider.color = self.colors['slider_selected']
            slider.track_color = self.colors['slider_track_unselected']

    def coeff_range_checkbox_events(self, *_):
        self.slider_colors('coeff_range_checkbox', 'coeff_slider')
        self.update_display()

    def time_range_checkbox_events(self, *_):
        self.slider_colors('time_range_checkbox', 'time_slider')
        self.update_display()

    def coeff_slider_events(self, *_):
        self.coeff_lower_bound.v_model = self.coeff_slider.v_model[0]
        self.coeff_upper_bound.v_model = self.coeff_slider.v_model[1]
        self.update_display()

    def time_slider_events(self, *_):
        self.time_lower_bound.v_model = self.time_slider.v_model[0]
        self.time_upper_bound.v_model = self.time_slider.v_model[1]
        self.update_display()

    def bound_boxes_events(self, *_):
        bounds = [self.coeff_lower_bound,
                  self.coeff_upper_bound,
                  self.time_lower_bound,
                  self.time_upper_bound]

        for x in bounds:
            try:
                float(x.v_model)
            except ValueError:
                x.error_messages = 'not a number'
                return

        if float(self.coeff_lower_bound.v_model) < -1:
            self.coeff_lower_bound.error_messages = 'out of range'
            return
        if float(self.coeff_upper_bound.v_model) > 1:
            self.coeff_upper_bound.error_messages = 'out of range'
            return
        if float(self.time_lower_bound.v_model) < self.time_shift_min:
            self.time_lower_bound.error_messages = 'out of range'
            return
        if float(self.time_upper_bound.v_model) > self.time_shift_max:
            self.time_upper_bound.error_messages = 'out of range'
            return

        self.coeff_lower_bound.error_messages = ''
        self.coeff_upper_bound.error_messages = ''
        self.time_lower_bound.error_messages = ''
        self.time_upper_bound.error_messages = ''

        self.coeff_slider.v_model = [float(self.coeff_lower_bound.v_model), float(self.coeff_upper_bound.v_model)]
        self.time_slider.v_model = [float(self.time_lower_bound.v_model), float(self.time_upper_bound.v_model)]
        self.update_display()

    def output_toggle_events(self, *_):
        self.visualization.children = [self.progress]
        self.update_display()

    def output_type_events(self, *_):
        self.visualization.children = [self.progress]
        self.update_display()

    def get_start_end_times(self):
        self.start_time = self.current_df.spy.start.tz_convert('utc').isoformat().replace('+00:00', 'Z')
        self.end_time = self.current_df.spy.end.tz_convert('utc').isoformat().replace('+00:00', 'Z')

    def signal_pairs_selected(self):
        self.signals_dict = self.current_df.spy.query_df.set_index('New Name').to_dict('index')
        self.signal_pairs_ids = []
        bool_df = self.get_boolean_df().copy()
        bool_df.columns = [self.signals_dict[x]['ID'] for x in bool_df.columns]
        bool_df.index = [self.signals_dict[x]['ID'] for x in bool_df.index]
        time_shifts_df = self.time_shifts_df.copy()
        time_shifts_df.columns = bool_df.columns
        time_shifts_df.index = bool_df.index
        for col in bool_df.columns:
            trues = bool_df.index[bool_df[col]].tolist()
            # By convention, the shifted signal is item 0 in the tuple and it's shifted by the time in pair_time_shifts
            pair_ids = [(col, sig) for sig in trues if (sig, col) not in self.signal_pairs_ids and col != sig]
            self.signal_pairs_ids.extend(pair_ids)

    def worksheet_input_params(self):
        self.signals_dict = self.current_df.spy.query_df.set_index('New Name').to_dict('index')
        self.signal_ids = [self.signals_dict[x]['ID'] for x in self.current_signals]
        self.signal_names = [self.signals_dict[x]['Name'] for x in self.current_signals]
        self.time_shifts = self.time_shifts_df[self.current_signals].loc[
            self.save_dialog.target_dropdown.v_model].values

    def dialog_button_on_click(self, *_):
        self.save_dialog.create_signals_dropdown_events()
        self.save_dialog.v_model = True

    def close_snackbar_events(self, *_):
        self.signals_created.v_model = False

    def run(self):
        # noinspection PyTypeChecker
        display(HTML("<style>.container { width:100% !important; }</style>"))
        display(HTML(self.additional_styles))
        self.app.children = [self.appBar, self.controls, self.visualization]

        callbacks = dict(
            time_shifts_switch=dict(event_name='change', callback_fn='time_shifts_switch_events'),
            max_time_shifts=dict(event_name='change', callback_fn='max_shifts_events'),
            output_values_toggle=dict(event_name='change', callback_fn='output_toggle_events'),
            coeff_range_checkbox=dict(event_name='change', callback_fn='coeff_range_checkbox_events'),
            time_range_checkbox=dict(event_name='change', callback_fn='time_range_checkbox_events'),
            coeff_slider=dict(event_name='change', callback_fn='coeff_slider_events'),
            time_slider=dict(event_name='change', callback_fn='time_slider_events'),
            coeff_lower_bound=dict(event_name='change', callback_fn='bound_boxes_events'),
            coeff_upper_bound=dict(event_name='change', callback_fn='bound_boxes_events'),
            time_lower_bound=dict(event_name='change', callback_fn='bound_boxes_events'),
            time_upper_bound=dict(event_name='change', callback_fn='bound_boxes_events'),
            output_type_toggle=dict(event_name='change', callback_fn='output_toggle_events'),
            dialog_button=dict(event_name='click', callback_fn='dialog_button_on_click'),
            close_snackbar=dict(event_name='click', callback_fn='close_snackbar_events'),
        )

        for widget_name, event_props in callbacks.items():
            widget = getattr(self, widget_name)
            widget.on_event(event_props['event_name'], getattr(self, event_props['callback_fn']))

        return self.app


class CreateSignalsMenu(v.Dialog):
    """
    This class creates an ipyvuetify Dialog window with the options required
    to create correlation and time shifted signals in Seeq
    """

    def __init__(self, parent, **kwargs):
        self.parent = parent
        self._signal_writing_counter = {signal: 0 for signal in self.parent.df.columns}
        self._condition_id = None
        self.dialog_instructions = v.Html(tag='p', children=[])

        self.target_dropdown = v.Select(label="Target signal", items=self.parent.current_signals, dense=True,
                                        outlined=True,
                                        color=self.parent.colors['seeq_primary'], filled=True, item_color='primary',
                                        v_model='',
                                        disabled=self.parent.export_disabled, class_='mt-3')

        self.create_signals = v.Btn(color='success', children=['Create signals'], v_on='tooltip.on',
                                    target="_blank", disabled=True, loading=False,
                                    class_='', style_='text-transform: capitalize;')

        self.create_signals_tooltip = v.Tooltip(bottom=True, v_slots=[{
            'name': 'activator',
            'variable': 'tooltip',
            'children': self.create_signals
        }], children=['Save time shifted signals to the Analysis worksheet'])

        self.output_display = v.Html(tag='p', children=[])
        self.create_signals_dropdown = v.Select(label="Select type of signals to create",
                                                items=['Create Correlation or Time Shift Signals',
                                                       'Shift Signals with Respect to a Target'],
                                                dense=True,
                                                outlined=True,
                                                color=self.parent.colors['seeq_primary'], filled=True,
                                                item_color='primary',
                                                v_model='Create Correlation or Time Shift Signals',
                                                disabled=self.parent.export_disabled, class_='mt-3')

        signal_options_btns = [
            dict(name='Cross-Correlations', v_model='', style_='text-transform: capitalize; min-width: 200px',
                 tooltip='Creates one signal of the Pearson correlation coefficient per signal pair selected'),
            dict(name='Time Shifts', v_model='', style_='text-transform: capitalize; min-width: 150px',
                 tooltip='Creates one signal per signal pair of the time shifts needed to maximize cross correlation'),
            dict(name='Correlations and Time Shifts', v_model='', style_='text-transform: capitalize; min-width: 250px',
                 tooltip='Creates one signal per signal pair of the maximized Pearson coefficient resulted '
                         'from dynamically shifting the signals')
        ]
        self.rolling_window_options = ToggleButtons(signal_options_btns, v_model=0, mandatory=True, tile=True,
                                                    color=self.parent.colors['seeq_primary'],
                                                    borderless=False, dense=True, class_='flex-wrap pt-1 pb-4',
                                                    style_='background: transparent;')

        self.rolling_window_options_container = v.Html(
            tag='div',
            class_='d-flex flex-row flex-wrap justify-space-between',
            children=[])

        self.signals_type_option_card = v.CardText(style_=self.parent.info_style, class_='pa-0',
                                                   children=[])

        # Input box for timespan of the sliding window
        self.window_size, self.window_size_tooltip = create_input_param_box(
            v_model='24 h', label="Window Size", color=self.parent.colors['seeq_primary'],
            style_='max-width: 120px; font-size: small; text-align-last: end;', class_='mr-5',
            tooltip='Enter the timespan of the sliding window (e.g. 1h, 2min) ')

        # Input box for period of the sliding window
        self.window_period, self.window_period_tooltip = create_input_param_box(
            v_model='6 h', label="Window Period", color=self.parent.colors['seeq_primary'],
            style_='max-width: 130px; font-size: small; text-align-last: end;', class_='mr-5',
            tooltip='Enter the period of the sliding window (e.g. 1h, 2min) ')

        # Input box for minimum correlation threshold
        self.corr_thrs, self.corr_thrs_tooltip = create_input_param_box(
            v_model='0.8', label="Correlation Threshold", color=self.parent.colors['seeq_primary'],
            style_='max-width: 130px; font-size: small; text-align-last: end;', class_='mr-5',
            tooltip='Enter the minimum acceptable correlation coefficient value to determine the time shifts')

        self.seeq_output_time_unit = v.Select(label="Signal time units",
                                              items=['seconds', 'minutes', 'hours', 'days', 'years'],
                                              dense=True,
                                              outlined=True,
                                              color=self.parent.colors['seeq_primary'], filled=True,
                                              item_color='primary',
                                              v_model='minutes',
                                              style_='max-width: 150px; font-size: small; text-align-last: end;',
                                              disabled=self.parent.export_disabled, class_='')

        self.create_signals_inputs = v.Html(tag='div',
                                            class_='d-flex flex-row flex-wrap pa-0',
                                            children=[])

        super().__init__(children=[
            v.Card(children=[
                v.CardTitle(class_='headline gray lighten-2', primary_title=True, children=[
                    "Create signals"
                ]),
                v.CardText(style_=self.parent.info_style, children=[
                    self.parent.info_message,
                    self.create_signals_dropdown,
                    self.rolling_window_options_container,
                    self.signals_type_option_card,
                    v.Html(tag='div', class_='d-flex flex-row justify-end',
                           children=[self.create_signals_tooltip]),
                    self.output_display
                ]),
            ])
        ], **kwargs)

        # callbacks
        self.target_dropdown.on_event('change', self.dropdown_events)
        self.corr_thrs.on_event('change', self.input_box_events)
        self.window_size.on_event('change', self.input_box_events)
        self.window_period.on_event('change', self.input_box_events)
        self.rolling_window_options.on_event('change', self.signal_type_checkboxes_events)
        self.create_signals_dropdown.on_event('change', self.create_signals_dropdown_events)
        self.create_signals.on_event('click', self.shifted_signals_btn_on_click)

    @property
    def condition_id(self):
        return self._condition_id

    @condition_id.setter
    def condition_id(self, value):
        self._condition_id = value

    @property
    def signal_writing_counter(self):
        return self._signal_writing_counter

    @signal_writing_counter.setter
    def signal_writing_counter(self, value):
        self._signal_writing_counter = value

    def check_invalid_input_boxes(self):
        self.create_signals.disabled = False
        if self.window_period.error_messages != '' or self.window_size.error_messages != '':
            self.create_signals.disabled = True

        if self.create_signals_dropdown.v_model in self.create_signals_dropdown.items:
            if self.corr_thrs.error_messages != '':
                self.create_signals.disabled = True

    def toggle_button_loading(self):
        self.create_signals.loading = not self.create_signals.loading
        self.create_signals.disabled = self.create_signals.loading

    def dropdown_events(self, *_):
        if self.target_dropdown.v_model != '':
            self.create_signals.disabled = False
        else:
            self.create_signals.disabled = True

    def input_box_events(self, widget, __, ___):
        self.create_signals.disabled = False
        if widget.label == 'Window Size' or widget.label == 'Window Period':
            widget.v_model, widget.error_messages, _ = validate_units(widget.v_model,
                                                                      time_shifts_on=True,
                                                                      auto_allowed=False)
        if widget.label == 'Correlation Threshold':
            try:
                widget.error_messages = ''
                val = float(widget.v_model)
                if val < 0:
                    widget.error_messages = 'Value must be greater than or equal to 0'
                if val > 1:
                    widget.error_messages = 'Value must be less than or equal to 1'

            except ValueError:
                widget.error_messages = 'Value must be float'

        self.check_invalid_input_boxes()

    def signal_type_checkboxes_events(self, *_):

        if self.rolling_window_options.v_model == 1 or self.rolling_window_options.v_model == 2:
            self.create_signals_inputs.children = [self.window_size_tooltip,
                                                   self.window_period_tooltip,
                                                   self.corr_thrs_tooltip,
                                                   self.seeq_output_time_unit]
            self.signals_type_option_card.children = ['Adjust the sliding window parameters and time '
                                                      'shifts options',
                                                      v.Html(tag='p'),
                                                      self.create_signals_inputs,
                                                      v.Html(tag='p')]
        elif self.rolling_window_options.v_model == 0:
            self.create_signals_inputs.children = [self.window_size_tooltip,
                                                   self.window_period_tooltip]
            self.signals_type_option_card.children = ['Adjust the sliding window parameters',
                                                      v.Html(tag='p'),
                                                      self.create_signals_inputs,
                                                      v.Html(tag='p')]
        self.check_invalid_input_boxes()

    def create_signals_dropdown_events(self, *_):
        if self.parent.export_disabled:
            self.export_disabled()
            return
        self.create_signals.disabled = False
        self.target_dropdown.disabled = False
        self.rolling_window_options.correlations_and_time_shifts.disabled = False
        self.rolling_window_options.time_shifts.disabled = False
        if self.create_signals_dropdown.v_model == self.create_signals_dropdown.items[0]:
            if not self.parent.time_shifts_switch.v_model:
                self.rolling_window_options.v_model = 0
                self.rolling_window_options.correlations_and_time_shifts.disabled = True
                self.rolling_window_options.time_shifts.disabled = True

            self.rolling_window_options_container.children = ["Select the type of signals to create",
                                                              self.rolling_window_options]
            self.create_signals_inputs.children = []
            self.signals_type_option_card.children = []
            self.signal_type_checkboxes_events()

        elif self.create_signals_dropdown.v_model == self.create_signals_dropdown.items[1]:
            self.rolling_window_options_container.children = []
            self.create_signals_inputs.children = [self.target_dropdown]
            if not self.parent.time_shifts_switch.v_model:
                self.signals_type_option_card.children = ['This option is not available if Time Shift is turned off']
                return

            self.signals_type_option_card.children = ['Shifts signals with respect to a target signal to '
                                                      'maximize cross correlations',
                                                      self.create_signals_inputs]
            if self.target_dropdown.v_model == '':
                self.create_signals.disabled = True

        else:
            self.create_signals.disabled = True

    def export_disabled(self):
        self.create_signals_dropdown.disabled = True
        self.rolling_window_options_container.children = []
        self.signals_type_option_card.children = []

    def shifted_signals_btn_on_click(self, *_):
        if self.parent.export_disabled:
            self.export_disabled()
            return
        if not hasattr(self.parent.current_df.spy, 'query_df'):
            self.parent.info_message = "The current signals do not have a corresponding Seeq ID. " \
                                       "Cannot create shifted signals."
            self.parent.info_style = "color: #ff5252 !important;"
            self.export_disabled()
            return

        self.toggle_button_loading()
        self.parent.get_start_end_times()
        if self.condition_id is None:
            self.condition_id = create_condition(self.parent.start_time, self.parent.end_time,
                                                 self.parent.workbook_id, spy.client,
                                                 capsule_name='Correlation Analysis')

        if self.create_signals_dropdown.v_model == self.create_signals_dropdown.items[1]:
            self.parent.worksheet_input_params()
            target = self.target_dropdown.v_model
            suffix_ = f'_{self.signal_writing_counter[target]}'
            suffix = f"{suffix_ if self.signal_writing_counter[target] > 0 else ''}"

            if self.target_dropdown.v_model == '':
                self.create_signals.disabled = True
            worksheet_with_lagged_signals(self.parent.signal_ids, self.parent.signal_names, self.parent.time_shifts,
                                          self.parent.time_unit, target, self.parent.workbook_id,
                                          self.parent.worksheet_id,
                                          self.parent.start_time,
                                          self.parent.end_time, False, spy.client, include_original_signals=True,
                                          suffix=suffix, condition_id=self.condition_id)

            self.signal_writing_counter[target] += 1

        if self.create_signals_dropdown.v_model == self.create_signals_dropdown.items[0]:

            if self.rolling_window_options.v_model == 0:
                corr_coeff_signals = True
                time_shifts_signals = False
            elif self.rolling_window_options.v_model == 1:
                corr_coeff_signals = False
                time_shifts_signals = True
            elif self.rolling_window_options.v_model == 2:
                corr_coeff_signals = True
                time_shifts_signals = True
            else:
                corr_coeff_signals = False
                time_shifts_signals = False

            self.parent.signal_pairs_selected()
            worksheet_name = f'Correlation Analysis {datetime.datetime.now(): %Y-%m-%d %H:%M:%S}'
            url = worksheet_corrs_and_time_shifts(self.parent.signal_pairs_ids, self.parent.workbook_id,
                                                  worksheet_name, self.parent.start_time, self.parent.end_time,
                                                  corr_coeff_signals=corr_coeff_signals,
                                                  time_shifted_for_correlation=self.parent.time_shifts_switch.v_model,
                                                  output_time_unit=self.seeq_output_time_unit.v_model,
                                                  max_time_shift=self.parent.actual_max_time_shift, suffix='',
                                                  time_shifts_signals=time_shifts_signals,
                                                  window_size=self.window_size.v_model,
                                                  period=self.window_period.v_model,
                                                  corr_thrs=self.corr_thrs.v_model,
                                                  condition_id=self.condition_id,
                                                  overwrite=True, api_client=spy.client,
                                                  datasource=None)

            # noinspection PyTypeChecker
            display(Javascript(f'window.open("{url}");'))

        self.v_model = False
        self.toggle_button_loading()
        self.parent.signals_created.v_model = True


class ToggleButtons(v.BtnToggle):
    """
    This is an auxiliary class to generate toggle buttons with a
    specific style and including a tooltip
    """

    def __init__(self, buttons_info: list, **kwargs):
        """
        Parameters
        ----------
        buttons_info: list
            List of dictionaries for the buttons to be bundle as toggles.
            Each dictionary in the list shall have the following keys
                Keys     |  Values
                -----------------
                name     | label of the button
                v_model  | initial value of the button
                tooltip  | a string of the tooltip
                style_   | CSS styling
        **kwargs:
            Any valid arguments of v.BtnToggle
        """

        v_btns = []
        for btn in buttons_info:
            v_btns.append(self.create_btn(btn['name'], btn['v_model'], btn['style_'], btn['tooltip']))

        super().__init__(children=v_btns, **kwargs)

    def create_btn(self, name, v_model, style_, tooltip):
        button = v.Btn(children=[name], v_model=v_model, depressed=True, v_on='tooltip.on',
                       small=True, style_=style_)
        setattr(self, name.lower().replace('-', '_').replace(' ', '_'), button)
        return v.Tooltip(top=True, v_slots=[{
            'name': 'activator',
            'variable': 'tooltip',
            'children': button
        }], children=[tooltip])


class HamburgerMenu(v.Menu):
    """
    This class creates the hamburger menu (with its options) used in the
    top-right corner of the Correlation Add-on.
    """

    def __init__(self, **kwargs):
        self.hamburger_button = v.AppBarNavIcon(v_on='menuData.on')
        self.help_button = v.ListItem(value='help',
                                      ripple=True,
                                      href=_github_issues,
                                      target="_blank",
                                      children=[v.ListItemAction(class_='mr-2 ml-0',
                                                                 children=[v.Icon(color='#212529',
                                                                                  children=['fa-life-ring'])]),
                                                v.ListItemActionText(children=[f'Send Support Request'])
                                                ])
        self.user_guide_button = v.ListItem(value='user_guide',
                                            ripple=True,
                                            href=_user_guide,
                                            target="_blank",
                                            children=[v.ListItemAction(class_='mr-2 ml-0',
                                                                       children=[v.Icon(color='#212529',
                                                                                        children=[
                                                                                            'fa fa-info-circle'])]),
                                                      v.ListItemActionText(children=[f'User Guide'])
                                                      ])
        self.items = [v.Divider(), self.user_guide_button, v.Divider(), self.help_button, v.Divider()]

        super().__init__(offset_y=True,
                         offset_x=False,
                         left=True,
                         v_slots=[{
                             'name': 'activator',
                             'variable': 'menuData',
                             'children': self.hamburger_button,
                         }]
                         ,
                         children=[
                             v.List(children=self.items)
                         ]
                         , **kwargs)

    # TODO: When tutorial is added. We will need the following code
    #     for item in self.items:
    #         item.on_event('click', self.on_menu_click)
    #
    # TODO: With this callback
    # def on_menu_click(self, widget, *_):
    #     print(widget.value)


def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier


def create_input_param_box(v_model='', label='', color='primary', style_='', class_='', tooltip=''):
    input_box = v.TextField(v_model=v_model, hide_details="auto", dense=True, style_=style_,
                            outlined=True, shaped=False, filled=True, label=label, color=color, hint='',
                            v_on='tooltip.on', class_=class_, error_messages='')
    input_box_tooltip = v.Tooltip(top=True, v_slots=[{
        'name': 'activator',
        'variable': 'tooltip',
        'children': input_box
    }], children=[tooltip])

    return input_box, input_box_tooltip


def create_checkbox(label='', color='primary', dense=True, class_='', style_='', id_='', v_model=False, tooltip=''):
    checkbox = v.Checkbox(id=id_, label=label, color=color, dense=dense, v_on='tooltip.on', class_=class_,
                          v_model=v_model, style_=style_)
    checkbox_tooltip = v.Tooltip(top=True, v_slots=[{
        'name': 'activator',
        'variable': 'tooltip',
        'children': checkbox
    }], children=[tooltip])

    return checkbox, checkbox_tooltip


def validate_units(v_model, time_shifts_on=True, auto_allowed=True):
    if not v_model:
        if time_shifts_on:
            max_time_str_error = 'value is required'
            return v_model, max_time_str_error, None
        else:
            max_time_str_error = ''
        time_output_unit = 's'
        return v_model, max_time_str_error, time_output_unit
    if auto_allowed:
        if v_model.strip() == 'auto':
            max_time_str_error = ''
            time_output_unit = 'auto'
            return v_model, max_time_str_error, time_output_unit

    max_time_str_error = None
    time_output_unit = None
    try:
        pd.Timedelta(v_model)
        max_time_str_error = ''
        reg = re.split(r'(\d+)[.]?', v_model.strip())
        time_output_unit = reg[-1].strip()
        if time_output_unit == '':
            if reg[-2].strip() == '0':
                time_output_unit = 's'
                v_model = '0s'
                max_time_str_error = ''
            else:
                max_time_str_error = 'invalid time unit'
    except ValueError as e:
        if 'unit abbreviation' or 'have leftover units' in e.args[0]:
            max_time_str_error = 'invalid time unit'

    return v_model, max_time_str_error, time_output_unit
