from timechart.plugin import *
from timechart import colors
from timechart.model import tcProcess
from enthought.traits.ui.api import View,Item,VGroup,Handler
from enthought.traits.api import Str,HasTraits

class cpu_hotplug_stats(HasTraits):
    def __init__ (self):
	self.count = 0
	self.last = 0
	self.avg = 0
	self.max = 0
	self.min = 1000000
	self.start = 0
	self.end = 0
	self.list = []
	self.list_pos = []

    def add_stat_element(self,timestamp):
	self.end = timestamp
	if self.start < self.end:
	    self.last = self.end - self.start
	    self.list.append(self.last)
	    self.list_pos.append(self.start)

	    self.max = max(self.list)
	    self.min = min(self.list)
	    self.avg = 0
	    self.count = len(self.list)
	    for i in self.list:
		self.avg += i
	    self.avg /= self.count

    def get_stats(self):
	return self.min,self.max,self.avg,self.count

    def get_pos(self,item):
	i = self.list.index(item)
	return self.list_pos[i]

class cpu_hotplug(plugin):
    down = cpu_hotplug_stats()
    adisable = cpu_hotplug_stats()
    adie = cpu_hotplug_stats()
    up = cpu_hotplug_stats()
    aup = cpu_hotplug_stats()
    statfile = Str("cpu_hotplug.dat")

    additional_colors = """
unplug        	#FF0000
cpu_hotplug_bg  #00FF00
"""
    additional_ftrace_parsers = [
	('cpu_hotplug_down_start',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_down_end',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_up_start',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_up_end',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_disable_start',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_disable_end',   'cpuid=%d', 'cpuid'),
	('cpu_hotplug_die_start',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_die_end',   'cpuid=%d', 'cpuid'),
	('cpu_hotplug_arch_up_start',  'cpuid=%d', 'cpuid'),
	('cpu_hotplug_arch_up_end',   'cpuid=%d', 'cpuid'),
	 ]

    additional_process_types = {
	"cpu_hotplug":(tcProcess, POWER_CLASS),
	}

    @staticmethod
    def create_filestat(self, stat):
	stat.statfile = self.filename + ".dat"
	fileHandle = open ( stat.statfile, 'w' )
	fileHandle.write ("         idx|arch_disable|    arch_die|        down|      arch_up|          up\n")
	fileHandle.write ("------------------------------------------------------------------------------\n")
	fileHandle.close()

    @staticmethod
    def add_filestat(self, stat):
	fileHandle = open ( stat.statfile, 'a' )
	fileHandle.write ("%12d "%(stat.up.count))
	if stat.adisable.count >= stat.up.count:
	    fileHandle.write ("%12d "%(stat.adisable.list[stat.up.count-1]))
	if stat.adie.count >= stat.up.count:
	    fileHandle.write ("%12d "%(stat.adie.list[stat.up.count-1]))
	if stat.down.count >= stat.up.count:
	    fileHandle.write ("%12d "%(stat.down.list[stat.up.count-1]))
	if stat.aup.count >= stat.up.count:
	    fileHandle.write ("%12d "%(stat.aup.list[stat.up.count-1]))
	if stat.up.count >= stat.up.count:
	    fileHandle.write ("%12d \n"%(stat.up.list[stat.up.count-1]))
	fileHandle.close()

    @staticmethod
    def do_event_cpu_hotplug_down_start(self,event):
	cpu_hotplug.down.start = event.timestamp

	process = self.generic_find_process(0,"cpu_hotplug:down:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_start(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_down_end(self,event):
	cpu_hotplug.down.add_stat_element(event.timestamp)

	process = self.generic_find_process(0,"cpu_hotplug:down:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_end(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_up_start(self,event):
	cpu_hotplug.up.start = event.timestamp

	process = self.generic_find_process(0,"cpu_hotplug:up:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_start(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_up_end(self,event):
	cpu_hotplug.up.add_stat_element(event.timestamp)

	if cpu_hotplug.up.count == 1:
	    cpu_hotplug.create_filestat(self, cpu_hotplug)
	cpu_hotplug.add_filestat(self, cpu_hotplug)

	process = self.generic_find_process(0,"cpu_hotplug:up:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_end(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_disable_start(self,event):
	cpu_hotplug.adisable.start = event.timestamp

	process = self.generic_find_process(0,"cpu_hotplug:arch_disable:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_start(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_disable_end(self,event):
	cpu_hotplug.adisable.add_stat_element(event.timestamp)

	process = self.generic_find_process(0,"cpu_hotplug:arch_disable:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_end(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_die_start(self,event):
	cpu_hotplug.adie.start = event.timestamp

	process = self.generic_find_process(0,"cpu_hotplug:arch_die:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_start(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_die_end(self,event):
	cpu_hotplug.adie.add_stat_element(event.timestamp)

	process = self.generic_find_process(0,"cpu_hotplug:arch_die:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_end(process,event,False)

	self.ensure_cpu_allocated(event.cpuid)
	tc = self.tmp_c_states[event.cpuid]
	if len(tc['start_ts'])>len(tc['end_ts']):
	    tc['end_ts'].append(event.timestamp)
	    self.missed_power_end +=1
	    if self.missed_power_end < 10:
		print "warning: missed hotplug_end"
	    if self.missed_power_end == 10:
		print "warning: missed hotplug_end: wont warn anymore!"
	tc['start_ts'].append(event.timestamp)
	tc['types'].append(colors.get_color_id('unplug'))

    @staticmethod
    def do_event_cpu_hotplug_arch_up_start(self,event):
	cpu_hotplug.aup.start = event.timestamp

	process = self.generic_find_process(0,"cpu_hotplug:arch_up:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_start(process,event,False)

    @staticmethod
    def do_event_cpu_hotplug_arch_up_end(self,event):
	cpu_hotplug.aup.add_stat_element(event.timestamp)

	process = self.generic_find_process(0,"cpu_hotplug:arch_up:%d"%(event.cpuid),"cpu_hotplug")
	self.generic_process_end(process,event,False)

	self.ensure_cpu_allocated(event.cpuid)
	tc = self.tmp_c_states[event.cpuid]
	if len(tc['start_ts'])>len(tc['end_ts']):
	    tc['end_ts'].append(event.timestamp)

plugin_register(cpu_hotplug)
