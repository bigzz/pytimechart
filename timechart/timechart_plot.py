from enthought.chaco.api import ArrayDataSource, DataRange1D, LinearMapper,BarPlot, LinePlot, \
                                 ScatterPlot, PlotAxis, PlotGrid,OverlayPlotContainer, VPlotContainer,add_default_axes, \
                                 add_default_grids,VPlotContainer
from enthought.chaco.tools.api import PanTool, ZoomTool,RangeSelection,RangeSelectionOverlay
from enthought.chaco.api import create_line_plot
from enthought.traits.ui.api import View,Item,VGroup
from enthought.traits.api import HasTraits,DelegatesTo,Trait
from enthought.traits.api import Float, Instance, Int,Bool,Str,Unicode,Enum,Button
from enthought.chaco.api import AbstractOverlay, BaseXYPlot
from enthought.chaco.label import Label
from enthought.kiva.traits.kiva_font_trait import KivaFont
from enthought.enable.api import black_color_trait

from timechart import TimechartProject, Timechart

from numpy import linspace,arange,amin,amax
from math import log
from numpy import array, ndarray,argmax,searchsorted,mean
from numpy import array, compress, column_stack, invert, isnan, transpose, zeros,ones
from enthought.traits.api import List
from enthought.enable.colors import ColorTrait
from enthought.pyface.timer import timer

c_states_colors=[0x000000,0xbbbbff,0x7777ff,0x5555ff,0x3333ff,0x1111ff,0x0000ff]
process_colors=[0x000000,0x555555,0xffff88,0x55ffff]
class TimeChartOptions(HasTraits):
    minimum_time_filter = Enum((0,1000,10000,50000,100000,500000,1000000,5000000,1000000,5000000,10000000,50000000))
    remove_pids_not_on_screen = Bool(False)
    show_wake_events = Bool(False)
    show_p_states = Bool(True)
    show_c_states = Bool(True)
    auto_zoom_y = Button()

    proj = TimechartProject

    traits_view = View(VGroup(
            Item('minimum_time_filter'),
            Item('remove_pids_not_on_screen'),
            Item('show_wake_events'),
            Item('show_p_states'),
            Item('show_c_states'),
            Item('auto_zoom_y'),
            label='Display Properties'
            ))
    def connect(self,plot):
        self.plot = plot
    def _minimum_time_filter_changed(self):
        self.plot.invalidate()
    def _remove_pids_not_on_screen_changed(self):
        self.plot.invalidate()
    def _show_wake_events_changed(self):
        self.plot.invalidate()
    def _show_p_states_changed(self):
        self.plot.invalidate()
    def _show_c_states_changed(self):
        self.plot.invalidate()
    def _auto_zoom_y_changed(self,val):
        self.plot.value_range.high = self.plot.max_y+1
        self.plot.value_range.low = self.plot.min_y    
        self.plot.invalidate_draw()
        self.plot.request_redraw()
class RangeSelectionTools(HasTraits):
    time = Str
    c_states = Str
    top_process = Str
    zoom = Button()
    traits_view = View(VGroup(
            Item('time'),
            Item('c_states'),
            Item('top_process'),
            Item('zoom'),
            label='Selection Infos'
            ))
    def connect(self,plot):
        self.plot = plot
        plot.range_selection.on_trait_change(self._selection_update_handler, "selection")
        self._timer = timer.Timer(100,self._selection_updated_delayed)
        self._timer.Stop()
    def _selection_update_handler(self,value):
        if value is not None :
            self.start, self.end = amin(value), amax(value)
            time = self.end-self.start
            self.time = "%d.%03d %03ds"%(time/1000000,(time/1000)%1000,time%1000)
            self._timer.Start()
    def _zoom_changed(self):
        self.plot.index_range.high = self.end
        self.plot.index_range.low = self.start
        self.plot.range_selection.deselect()
        self.plot.invalidate_draw()
        self.plot.request_redraw()
        
    def _selection_updated_delayed(self):
        #@todo here we need to update c_states and top_process stats.
	self.c_states= "not yet implemented"
	self.top_process= "not yet implemented"
        self._timer.Stop()
        pass
class TimeChartPlot(BarPlot):
    """custom plot to draw the timechart
    probably not very 'chacotic' We draw the chart as a whole
    """
    # the colors of the values
    c_states_colors = List(ColorTrait)
    process_colors = List(ColorTrait)
    # The text of the axis title.
    title = Trait('', Str, Unicode) #May want to add PlotLabel option
    # The font of the title.
    title_font = KivaFont('modern 9')
    # The font of the title.
    title_font_large = KivaFont('modern 15')
    # The spacing between the axis line and the title
    title_spacing = Trait('auto', 'auto', Float)
    # The color of the title.
    title_color = ColorTrait("black")
    
    options = TimeChartOptions()
    range_tools = RangeSelectionTools()
    def invalidate(self):
        self.invalidate_draw()
        self.request_redraw()


    def _gather_timechart_points(self,tc,y):
        low_i = searchsorted(tc.end_ts,self.index_mapper.range.low)
        high_i = searchsorted(tc.start_ts,self.index_mapper.range.high)
        
        if low_i==high_i:
            return array([])

        start_ts = tc.start_ts[low_i:high_i]
        end_ts = tc.end_ts[low_i:high_i]
        points = column_stack((start_ts,end_ts,
                               zeros(high_i-low_i)+(y+.2), ones(high_i-low_i)+(y-.2),array(range(low_i,high_i))))
        return points
    def _draw_label(self,gc,label,text,x,y):
        label.text = text
        l_w,l_h = label.get_width_height(gc)
        offset = array((x,y-l_h/2))
        gc.translate_ctm(*offset)
        label.draw(gc)
        gc.translate_ctm(*(-offset))
        return l_w,l_h
    def _draw_timechart(self,gc,tc,label,y,fill_colors):
        bar_middle_y = self.first_bar_y+(y+.5)*self.bar_height
        if bar_middle_y+self.bar_height < self.y or bar_middle_y-self.bar_height>self.y+self.height:
            return 1 #quickly decide we are not on the screen
        points = self._gather_timechart_points(tc,y)
        if self.options.remove_pids_not_on_screen and points.size == 0:
            return 0
        # we are too short in height, dont display all the labels
        if self.last_label >= bar_middle_y:
            self._draw_bg(gc,y,tc.bg_color)
            # draw label
            l_w,l_h = self._draw_label(gc,label,tc.name,self.x,bar_middle_y)
            self.last_label = bar_middle_y-(l_h*2/3)
        else:
            l_w,l_h = 0,0 
        if points.size != 0:
            # draw the middle line from end of label to end of screen
            if l_w != 0: # we did not draw label because too short on space
                gc.set_alpha(0.2)
                gc.move_to(self.x+l_w,bar_middle_y)
                gc.line_to(self.x+self.width,bar_middle_y)
                gc.draw_path()
            gc.set_alpha(0.5)
            # map the bars start and stop locations into screen space
            lower_left_pts = self.map_screen(points[:,(0,2)])
            upper_right_pts = self.map_screen(points[:,(1,3)])
            bounds = upper_right_pts - lower_left_pts

            if points.size>1000: # critical path, we only draw unicolor rects
                #calculate the mean color
                t = mean(tc.types[points[0][4]:points[-1][4]])
                gc.set_fill_color(fill_colors[int(t)])
                rects=column_stack((lower_left_pts, bounds))
                gc.rects(rects)
                gc.draw_path()
                return 1
            # lets display them more nicely
            rects=column_stack((lower_left_pts, bounds,points[:,(4)]))
            last_t = -1
            gc.save_state()
            for x,y,sx,sy,i in rects:
                t = tc.types[i]
                
                if last_t != t:
                    # only draw when we change color. agg will then simplify the path
                    # note that a path only can only have one color in agg.
                    gc.draw_path()
                    if len(fill_colors)>t:
                        gc.set_fill_color(fill_colors[int(t)])
                    last_t = t
                gc.rect(x,y,sx,sy)
            # draw last path
            gc.draw_path()
            if tc.has_comments:
                for x,y,sx,sy,i in rects:
                    if sx<8: # not worth calculatig text size
                        continue
                    label.text = tc.get_comment(i)
                    l_w,l_h = label.get_width_height(gc)
                    if l_w < sx:
                        offset = array((x,y+self.bar_height*.6/2-l_h/2))
                        gc.translate_ctm(*offset)
                        label.draw(gc)
                        gc.translate_ctm(*(-offset))
        return 1
            
    def _draw_freqchart(self,gc,tc,label,y):
        self._draw_bg(gc,y,tc.bg_color)
        low_i = searchsorted(tc.start_ts,self.index_mapper.range.low)
        high_i = searchsorted(tc.start_ts,self.index_mapper.range.high)

        if low_i>0:
            low_i -=1
        if high_i<len(tc.start_ts):
            high_i +=1
        
        if low_i>=high_i-1:
            return array([])
        
        start_ts = tc.start_ts[low_i:high_i-1]
        end_ts = tc.start_ts[low_i+1:high_i]
        values = (tc.types[low_i:high_i-1]/(float(tc.max_types)))+y
        starts = column_stack((start_ts,values))
        ends = column_stack((end_ts,values))
        starts = self.map_screen(starts)
        ends = self.map_screen(ends)
        gc.begin_path()
        gc.line_set(starts, ends)
        gc.stroke_path()
        for i in xrange(len(starts)):
            x1,y1 = starts[i]
            x2,y2 = ends[i]
            sx = x2-x1
            if sx >8:
                label.text = str(tc.types[low_i+i])
                l_w,l_h = label.get_width_height(gc)
                if l_w < sx:
                    if x1<0:x1=0
                    offset = array((x1,y1))
                    gc.translate_ctm(*offset)
                    label.draw(gc)
                    gc.translate_ctm(*(-offset))
    def _draw_wake_ups(self,gc,processes_y):
        low_i = searchsorted(self.proj.wake_events['time'],self.index_mapper.range.low)
        high_i = searchsorted(self.proj.wake_events['time'],self.index_mapper.range.high)
        gc.set_stroke_color((0,0,0,.6))
        for i in xrange(low_i,high_i):
            waker,wakee,ts = self.proj.wake_events[i]
            if processes_y.has_key(wakee) and processes_y.has_key(waker):
                y1 = processes_y[wakee]
                y2 = processes_y[waker]
                x,y = self.map_screen(array((ts,y1)))
                gc.move_to(x,y)
                y2 = processes_y[waker]
                x,y = self.map_screen(array((ts,y2)))
                gc.line_to(x,y)
                x,y = self.map_screen(array((ts,(y1+y2)/2)))
                if y1 > y2:
                    y+=5
                    dy=-5
                else:
                    y-=5
                    dy=+5
                gc.move_to(x,y)
                gc.line_to(x-3,y+dy)
                gc.move_to(x,y)
                gc.line_to(x+3,y+dy)

        gc.draw_path()
    def _draw_bg(self,gc,y,color):
        gc.set_alpha(1)
        gc.set_line_width(0)
        gc.set_fill_color(color)
        this_bar_y = self.map_screen(array((0,y)))[1]
        gc.rect(self.x, this_bar_y, self.width, self.bar_height)
        gc.draw_path()
        gc.set_line_width(self.line_width)
        gc.set_alpha(0.5)

    def _draw_plot(self, gc, view_bounds=None, mode="normal"):
        gc.save_state()
        gc.clip_to_rect(self.x, self.y, self.width, self.height)
        gc.set_antialias(1)
        gc.set_stroke_color(self.line_color_)
        gc.set_line_width(self.line_width)
        self.first_bar_y = self.map_screen(array((0,0)))[1]
        self.last_label = self.height
        self.bar_height = self.map_screen(array((0,1)))[1]-self.first_bar_y
        self.max_y = y = self.proj.num_cpu*2+self.proj.num_process-1
        if self.bar_height>15:
            font = self.title_font_large
        else:
            font = self.title_font
        label = Label(text="",
                      font=font,
                      color=self.title_color,
                      rotate_angle=0)
        for i in xrange(len(self.proj.c_states)):
            tc = self.proj.c_states[i]
            if self.options.show_c_states:
                self._draw_timechart(gc,tc,label,y,self.c_states_colors)
                y-=1
            tc = self.proj.p_states[i]
            if self.options.show_p_states:
                self._draw_freqchart(gc,tc,label,y)
                y-=1
        processes_y = {0xffffffffffffffffL:y+1}
        for tc in self.proj.processes:
            if tc.total_time < self.options.minimum_time_filter:
                continue
            processes_y[(tc.comm,tc.pid)] = y+.5
            if self._draw_timechart(gc,tc,label,y,self.process_colors) or not self.options.remove_pids_not_on_screen:
                y-=1
        if self.options.show_wake_events:
            self._draw_wake_ups(gc,processes_y)
        gc.restore_state()
        self.min_y = y
class myZoomTool(ZoomTool):
    """ a zoom tool which change y range only when control is pressed"""
    def normal_mouse_wheel(self, event):
        if event.control_down:
            self.tool_mode = "box"
        else:
            self.tool_mode = "range"
        super(myZoomTool, self).normal_mouse_wheel(event)
        # restore default zoom mode
        if event.control_down:
            self.tool_mode = "range"
def create_timechart_container(project):
    """ create a vplotcontainer which connects all the inside plots to synchronize their index_range """

    # find index limits
    low = 1<<64
    high = 0
    for i in xrange(len(project.c_states)):
        if len(project.c_states[i].start_ts):
            low = min(low,project.c_states[i].start_ts[0])
            high = max(high,project.c_states[i].end_ts[-1])
        if len(project.p_states[i].start_ts):
            low = min(low,project.p_states[i].start_ts[0])
            high = max(high,project.p_states[i].start_ts[-1])
    for tc in project.processes:
        if len(tc.start_ts):
            low = min(low,tc.start_ts[0])
            high = max(high,tc.end_ts[-1])

    # we have the same x_mapper/range for each plots
    index_range = DataRange1D(low=low, high=high)
    index_mapper = LinearMapper(range=index_range,domain_limit=(low,high))
    value_range = DataRange1D(low=0, high=project.num_cpu*2+project.num_process)
    value_mapper = LinearMapper(range=value_range,domain_limit=(0,project.num_cpu*2+project.num_process))
    index = ArrayDataSource(array((low,high)), sort_order="ascending")
    plot = TimeChartPlot(index=index,
                         proj=project, bgcolor="white",padding=(0,0,0,40),
                         use_backbuffer = True,
                         fill_padding = True,
                         value_mapper = value_mapper,
                         index_mapper=index_mapper,
                         line_color="black",
                         c_states_colors=c_states_colors,
                         process_colors=process_colors,
                         render_style='hold',
                         line_width=1)
    max_process = 50
    if value_range.high>max_process:
        value_range.low = value_range.high-max_process
    # Attach some tools 
    plot.tools.append(PanTool(plot,drag_button='left'))
    zoom = myZoomTool(component=plot, tool_mode="range", always_on=True,axis="index",drag_button=None)
    plot.tools.append(zoom)

    plot.range_selection = RangeSelection(plot,resize_margin=1,left_button_selects=False)
    plot.tools.append(plot.range_selection)
    plot.overlays.append(RangeSelectionOverlay(component=plot,axis="index",use_backbuffer=True))

    axe = PlotAxis(orientation='bottom',title='time',mapper=index_mapper,component=plot)
    plot.underlays.append(axe)
    plot.options.connect(plot)
    plot.range_tools.connect(plot)

    return plot