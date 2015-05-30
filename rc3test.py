#!/usr/bin/python
'''Test script for RC3 flow completion times vs regular completion times.

Also includes tests to show priority queue implementation correctness.'''

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import lg
from mininet.link import TCLink
from mininet.util import pmonitor
from mininet.cli import CLI
from time import time
from time import sleep
from signal import SIGINT
from argparse import ArgumentParser
from subprocess import PIPE, Popen
import subprocess
import json
import os
import matplotlib.pyplot as plt
from figure15_helpers import *


parser = ArgumentParser(description="CS244 Spring '15, RC3 Test")
parser.add_argument('--num-flows', '-n',
                    dest="num_flows",
                    type=int,
                    action="store",
                    help="Number of flows of a each size to measure "
                         "for each flow completion time test configuration.",
                    default=10,
                    required=False)

parser.add_argument('--dir', '-d',
                    dest="output_dir",
                    action="store",
                    help="Directory to store outputs",
                    default="results",
                    required=False)

# Expt parameters
args = parser.parse_args()

if not os.path.exists(args.output_dir):
    os.makedirs(args.output_dir)

# Below are the settings used to produce Figures 15 (a) and (b)
# from the paper, with original data and additional Mininet tests.
# Actual experiment used 10Gbps and 1Gbps rates with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product
RC3_fct_test_configs = [
    # Figure 15(a)
    # 10Gbps x 20us RTT test, scaled rate down by 100, delay up by 100
    # TCP Reno
    {
        'tcp_type': 'reno',
        'bandwidth': 100, # 100 Mbps
        'delay': '1000ms', # Delay is only at the host.
        'time_scale_factor': 1.0/100.0, # Rate by 1/100, delay by 100
        'flows_per_test': args.num_flows,
        'starter_data_function': figure15a_paper_data,
        'fig_file_name': args.output_dir + '/figure_15a_reno.png',
        'fct_offset': 0.010 # 1/2 RTT adjustment to match with paper method.
    },
    # TCP Cubic
    {
        'tcp_type': 'cubic',
        'bandwidth': 100, # 100 Mbps
        'delay': '1000ms', # Delay is only at the host.
        'time_scale_factor': 1.0/100.0, # Rate by 1/100, delay by 100
        'flows_per_test': args.num_flows,
        'starter_data_function': figure15a_paper_data,
        'fig_file_name': args.output_dir + '/figure_15a_cubic.png',
        'fct_offset': 0.010 # 1/2 RTT adjustment to match with paper method.
    },
    # Figure 15(b)
    # 1Gbps x 20us RTT test, scaled rate down by 10, delay up by 10
    # TCP Reno
    {
        'tcp_type': 'reno',
        'bandwidth': 100, # 10 Mbps
        'delay': '100ms', # Delay is only at the host.
        'time_scale_factor': 1.0/10.0, # Rate by 1/100, delay by 100
        'flows_per_test': args.num_flows,
        'starter_data_function': figure15b_paper_data,
        'fig_file_name': args.output_dir + '/figure_15b_reno.png',
        'fct_offset': 0.010 # 1/2 RTT adjustment to match with paper method.
    },
    # TCP Cubic
    {
        'tcp_type': 'cubic',
        'bandwidth': 100, # 10 Mbps
        'delay': '100ms', # Delay is only at the host.
        'time_scale_factor': 1.0/10.0, # Rate by 1/100, delay by 100
        'flows_per_test': args.num_flows,
        'starter_data_function': figure15b_paper_data,
        'fig_file_name': args.output_dir + '/figure_15b_cubic.png',
        'fct_offset': 0.010 # 1/2 RTT adjustment to match with paper method.
    }
]

class PrioSwitchTestTopo(Topo):
    '''Topology for testing priority queues on a switch.'''
    def __init__(self, bandwidth, delay):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        switch = self.addSwitch('s1')

        # Add links
        self.addLink(h1, switch, bw=bandwidth, delay=delay, use_htb=True)
        self.addLink(h2, switch, bw=bandwidth, delay=delay, use_htb=True)
        self.addLink(switch, h3, bw=bandwidth, delay=delay, use_htb=True)


class PrioTestTopo(Topo):
    '''Topology for testing priority queues on a host.'''
    def __init__(self, bandwidth, delay):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Add links
        self.addLink(h1, h2, bw=bandwidth, delay=delay, use_htb=True)

class RC3Topo(Topo):
    '''Topology for testing RC3 flow completion times, including a switch.'''
    def __init__(self, bandwidth):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        switch = self.addSwitch('s1')

        # Add links. Note: Delay, etc, inserted by custom prio qdisc code
        self.addLink(h1, switch, bw=bandwidth, use_htb=True)
        self.addLink(switch, h2, bw=bandwidth, use_htb=True)

def addPrioQdisc(node, devStr, bandwidth, delay=None):
    '''Setup the HTB, prio qdisc, netem, etc.

    node: Network node, e.g. h1, h2, s1.
    devStr: Device name string, e.g. 'h1-eth0'.
    bandwidth: A number, representing bandwidth in Mbps.
    delay: A string, such as 10us, or None for no delay.
    '''

    print devStr, "Initial tc Configuration ==========================="
    node.cmdPrint('tc qdisc show dev', devStr)
    node.cmdPrint('tc class show dev', devStr)

    print devStr, "Setting tc Configuration ==========================="
    node.cmdPrint('tc qdisc del dev', devStr, 'root');
    node.cmdPrint('tc qdisc add dev', devStr, 'root handle 1: htb default 1')
    # TODO
    print "TODO: Set burst rates to match original?"
    rate = "%fMbit" % bandwidth
    node.cmdPrint('tc class add dev', devStr, 'classid 1:1 parent 1: htb rate',
                  rate, 'ceil', rate)
    # prio qdisc for priority queues. priomap mostly ignored, use filters below
    node.cmdPrint('tc qdisc add dev', devStr,
                  'parent 1:1 handle 2:0 prio bands 8 '
                  'priomap 0 1 2 3 4 5 6 7 7 7 7 7 7 7 7 7')
    # netem qdiscs at leaves if delay is wanted.
    if delay is not None:
        for i in range(1, 5+1):
            node.cmdPrint('tc qdisc add dev %s parent 2:%d handle 15%d:'
                          ' netem delay %s limit 1000' % (devStr, i, i, delay))
    # filters to match the ToS bit settings used by RC3 and put in prio queues
    for (i,tos) in zip(range(1, 5+1), ['0x00','0x04','0x08','0x0c','0x10']):
        node.cmdPrint('tc filter add dev %s parent 2:0 protocol ip'
                      ' prio 10 u32 match ip tos %s 0xff flowid 2:%d'
                      % (devStr, tos, i))

    print devStr, "Custom tc Configuration ============================"

    node.cmdPrint('tc qdisc show dev', devStr)
    node.cmdPrint('tc class show dev', devStr)
    node.cmdPrint('tc filter show dev', devStr, 'parent 15:0')
    #node.cmdPrint('tc -s class ls dev', devStr)

def runPrioSwitchFlows(bandwidth, delay, interval, duration, loOut, hiOut, loFirst):
    '''Create a mininet simulation, and test priority queues on a switch.

    Starts a high or low priority flow from one host to a receiver, through
    the switch. At half the duration, the other host starts another flow
    through the switch to the same receiver, but with the other priority level.
    Records JSON outputs for later parsing.

    Args:
        bandwidth: A number, representing bandwidth of each link in Mbps.
        delay: A string, such as 10us, or None for no delay.
        interval: Number of seconds between each iperf3 output.
        duration: Total duration of test, in seconds.
        loOut: Iperf3 output file name for low priority flow information.
        hiOut: Iperf3 output file name for high priority flow information.
        loFirst: Boolean, whether low priority flow starts first or not.
    '''
    topo = PrioSwitchTestTopo(bandwidth, delay)
    net = Mininet(topo, link=TCLink)
    net.start()

    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2, h3, s1 = net.getNodeByName('h1', 'h2', 'h3', 's1')

    print "Adding qdiscs"
    addPrioQdisc(h1, 'h1-eth0', bandwidth=bandwidth)
    addPrioQdisc(h2, 'h2-eth0', bandwidth=bandwidth)
    addPrioQdisc(h3, 'h3-eth0', bandwidth=bandwidth)
    addPrioQdisc(s1, 's1-eth1', bandwidth=bandwidth)
    addPrioQdisc(s1, 's1-eth2', bandwidth=bandwidth)
    addPrioQdisc(s1, 's1-eth3', bandwidth=bandwidth)

    h1.cmd('killall iperf3')
    h2.cmd('killall iperf3')
    h3.cmd('killall iperf3')

    ps = {} # ProcesseS

    print "Testing bandwidth with high and low priority flows..."
    ps['hiserv'] = h3.popen('iperf3 -s -p 5001 -1 -i %f -J > %s' \
                % (interval, hiOut), shell=True)
    ps['loserv'] = h3.popen('iperf3 -s -p 5002 -1 -i %f -J > %s' \
                % (interval, loOut), shell=True)


    if loFirst:
        print 'launching low priority iperf'
        ps['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' \
                % (h3.IP(), interval, duration+1), shell=True)
    else:
        print 'launching high priority iperf'
        ps['hiperf'] = h2.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0 -J' \
                % (h3.IP(), interval, duration+1), shell=True)

    sleep(duration/ 2)

    if loFirst:
        print 'launching high priority iperf'
        ps['hiperf'] = h2.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0 -J' \
                % (h3.IP(), interval, (duration/2)+1), shell=True)
    else:
        print 'launching low priority iperf'
        ps['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' \
                % (h3.IP(), interval, (duration/2)+1), shell=True)

    ps['hiperf'].wait()
    ps['loperf'].wait()
    ps['hiserv'].wait()
    ps['loserv'].wait()
    print 'flows finished'

    net.stop()

def prioSwitchTest(bandwidth, delay, interval, duration):
    '''Test priority queues on a switch topo, producing a pair of graphs.

    Starts a high or low priority flow from one host to a receiver, through
    the switch. At half the duration, the other host starts another flow
    through the switch to the same receiver, but with the other priority level.

    Args:
        bandwidth: A number, representing bandwidth of each link in Mbps.
        delay: A string, such as 10us, or None for no delay.
        interval: Number of seconds between each iperf3 output.
        duration: Total duration of test, in seconds.
    '''
    odir = args.output_dir
    runPrioSwitchFlows(bandwidth, delay, interval, duration,
                       odir + '/sservlo1.json', odir + '/sservhi1.json', False)
    runPrioSwitchFlows(bandwidth, delay, interval, duration,
                       odir + '/sservlo2.json', odir + '/sservhi2.json', True)
    iperfPlotJSON(odir + '/sservlo1.json',odir + '/sservhi1.json',
                  odir + '/sservlo2.json', odir + '/sservhi2.json',
                  odir + '/figure_17.png', duration,
                  'Correctness of Priority Queueing in the Switch')

def iperfParseJSON(filename, duration, offset):
    '''
    Parse JSON output from iperf3 and return arrays of times and bandwidths.

    Args:
        filename: Input JSON file name.
        duration: Number of seconds in the file.
        offset: Offset to apply to time values, for flows started later.
    '''
    X = []
    Y = []
    with open(filename) as f:
        a = json.load(f)
    for interval in a['intervals']:
        stream = interval['streams'][0]
        if stream['end'] + offset <= duration:
            X.append(stream['end'] + offset)
            Y.append(stream['bits_per_second'] / 1000000.0)

    return (X, Y)

def iperfPlotJSON(lofile1, hifile1, lofile2, hifile2, outfile, duration,
                  title):
    '''
    Plot four json files and output as outfile.

    Args:
        lofile1, hifile1: Flow files for the first test (low priority starts
            after high priority).
        lofile2 hifile2: Flow files for the the second test (high priority
            starts after low priority).
        duration: Number of seconds in the test.
        title: Title to use for the plot.
    '''
    plt.clf()
    plt.cla()

    plt.figure(figsize=(13, 5))
    plt.suptitle(title)

    plt.subplot(121)
    plt.xlabel('Time (s)')
    plt.ylabel('Throughput (Mbps)')

    loData = iperfParseJSON(lofile1, duration, duration/2)
    loX = loData[0]
    loY = loData[1]
    print('loY: ', loY)

    plt.plot(loX, loY, linewidth=2.0, label='Low Priority')

    hiData = iperfParseJSON(hifile1, duration, 0)
    hiX = hiData[0]
    hiY = hiData[1]
    print('hiY: ', hiY)
    plt.plot(hiX, hiY, linewidth=2.0, label='High Priority')

    plt.legend(loc='lower left')


    plt.subplot(122)
    plt.xlabel('Time (s)')
    plt.ylabel('Throughput (Mbps)')

    loData = iperfParseJSON(lofile2, duration, 0)
    loX = loData[0]
    loY = loData[1]
    plt.plot(loX, loY, linewidth=2.0, label='Low Priority')
    print('loY: ', loY)

    hiData = iperfParseJSON(hifile2, duration, duration/2)
    hiX = hiData[0]
    hiY = hiData[1]
    plt.plot(hiX, hiY, linewidth=2.0, label='High Priority')
    print('hiY: ', hiY)

    plt.legend(loc='lower left')


    plt.savefig(outfile, bbox_inches='tight')
    print('plot saved to ', outfile)

def runPrioFlows(bandwidth, delay, interval, duration, loOut, hiOut, loFirst):
    '''Create a mininet simulation, and test priority queues on a host.

    Starts a high or low priority flow from one host to a receiver. At half
    the duration, the other host starts another flow to the same receiver, but
    with the other priority level. Records JSON outputs for later parsing.

    Args:
        bandwidth: A number, representing bandwidth of each link in Mbps.
        delay: A string, such as 10us, or None for no delay.
        interval: Number of seconds between each iperf3 output.
        duration: Total duration of test, in seconds.
        loOut: Iperf3 output file name for low priority flow information.
        hiOut: Iperf3 output file name for high priority flow information.
        loFirst: Boolean, whether low priority flow starts first or not.
    '''
    topo = PrioTestTopo(bandwidth, delay)
    net = Mininet(topo, link=TCLink)
    net.start()

    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2 = net.getNodeByName('h1', 'h2')

    print "Adding qdiscs"
    addPrioQdisc(h1, 'h1-eth0', bandwidth=bandwidth)
    addPrioQdisc(h2, 'h2-eth0', bandwidth=bandwidth)

    h1.cmd('killall iperf3')
    h2.cmd('killall iperf3')

    ps = {} # ProcesseS

    print "Testing bandwidth with high and low priority flows..."
    ps['hiserv'] = h2.popen('iperf3 -s -p 5001 -1 -i %f -J > %s' \
                % (interval, hiOut), shell=True)
    ps['loserv'] = h2.popen('iperf3 -s -p 5002 -1 -i %f -J > %s' \
                % (interval, loOut), shell=True)

    if loFirst:
        print 'launching low priority iperf'
        ps['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' \
                % (h2.IP(), interval, duration+1), shell=True)
    else:
        print 'launching high priority iperf'
        ps['hiperf'] = h1.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0 -J' \
                % (h2.IP(), interval, duration+1), shell=True)

    sleep(duration/ 2)

    if loFirst:
        print 'launching high priority iperf'
        ps['hiperf'] = h1.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0 -J' \
                % (h2.IP(), interval, (duration/2)+1), shell=True)
    else:
        print 'launching low priority iperf'
        ps['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' \
                % (h2.IP(), interval, (duration/2)+1), shell=True)

    ps['hiperf'].wait()
    ps['loperf'].wait()
    ps['hiserv'].wait()
    ps['loserv'].wait()
    print 'flows finished'

    net.stop()

def prioTest(bandwidth, delay, interval, duration):
    '''Test priority queues on a host (no switchs), producing a pair of graphs.

    Starts a high or low priority flow from one host to a receiver. At half
    the duration, the other host starts another flow to the same receiver,
    but with the other priority level.

    Args:
        bandwidth: A number, representing bandwidth of each link in Mbps.
        delay: A string, such as 10us, or None for no delay.
        interval: Number of seconds between each iperf3 output.
        duration: Total duration of test, in seconds.
    '''
    odir = args.output_dir
    runPrioFlows(bandwidth, delay, interval, duration,
                 odir + '/servlo1.json', odir + '/servhi1.json', False)
    runPrioFlows(bandwidth, delay, interval, duration,
                 odir + '/servlo2.json', odir + '/servhi2.json', True)
    iperfPlotJSON(odir + '/servlo1.json', odir + '/servhi1.json',
                  odir + '/servlo2.json', odir + '/servhi2.json',
                  odir + '/figure_16.png', duration,
                  'Correctness of Priority Queueing in Linux')

def do_fct_tests(net, iterations, time_scale_factor, starter_data_function,
                 fig_file_name, fct_offset):
    '''Run a series of flow completion time tests, and make a bar chart.

    Args:
        net: Mininet net object.
        iterations: Number of times to test FCT at a given setting, before
            taking mean and stddev.
        time_scale_factor: FCTs will be scaled by this amount, to normalize
            results. I.e. if link delay is scaled by 10, scale_factor should
            probably be 1/10.
        starter_data_function: The name of a function which will give a data
            structure for plotting. This is used to get the data from the paper
            figures 15(a) and 15(b). See figure15_helpers.py.
        fig_file_name: If specified, where to save the resulting plot.
        fct_offset: Offset time (in post-scaling units) to adjust for
            difference in measuring technique.
    '''

    # Flow lengths for the flow completion times.
    flow_lengths = [1460, 7300, 14600, 73000, 146000, 730000, 1460000]
    # For debug:
    #flow_lengths = [730000]

    # Start with the bar-graph data from the paper
    (data, flow_types, flow_type_colors, title) = starter_data_function()

    # Do flow-completion-time tests for each flow length,
    # using regular TCP and rc3, and add to graph data structure
    for flow_length in flow_lengths:
        for (rc3, flow_type) in [(False, 'Mininet Regular TCP'),
                                 (True,  'Mininet RC3')]:
            results = fct_test(net, iterations=iterations, size=flow_length,
                               use_rc3=rc3)
            print "results", results
            o = fct_offset
            s = time_scale_factor * 0.001 # external scale and msecs to secs
            data[flow_length][flow_type] = {'mean'  : o + s * avg(results),
                                            'stddev': s * stddev(results)}

    plotBarClusers(data, flow_types, flow_type_colors, title, fig_file_name)

def fct_test(net, skip = 2, size = 1024*1024, iterations = 10, use_rc3=False):
    '''Run the fcttest multiple times, return list of times in milliseconds.

    Args:
        net: Mininet net object.
        skip: The number of initial tests to run without including in results.
        size: Size of the flow, in bytes.
        iterations: Number of tests to do / results to attempt to return.
        use_rc3: If True, use RC3 instead of normal TCP.
    '''

    results = []

    h1, h2 = net.getNodeByName('h1', 'h2')

    rc3_arg_setting = "-r" if use_rc3 else ""

    # Start server
    p_srv = h2.popen('./fcttest -s -p 5678 -g %d %s' % (size, rc3_arg_setting),
                     stdout = subprocess.PIPE, stderr = subprocess.PIPE)

    # Run the client iterations + skip times
    for i in range(0,iterations + skip):
        p_clt = h1.popen('./fcttest -c -a %s -p 5678 -g %d %s'
                         % (h2.IP(), size, rc3_arg_setting),
                         stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        (out, err) = p_clt.communicate()
        if err or p_clt.returncode != 0:
            print "[ERROR]: fcttest client error:", err
        else:
            skip_this = i < skip
            time = float(out)
            print "skip_this = %s, use_rc3 = %s, size = %d, time (ms) = %f" \
                   % (skip_this, str(use_rc3), size, time)
            if not skip_this:
               results.append(time)

    # Kill the server
    if p_srv.poll() is None:
      p_srv.kill()
    else:
      (out, err) = p_srv.communicate()
      print "[ERROR]: fcttest error: %s" % err

    return results

def setupNetVariables():
    '''Setup Linux networking variables.

    As prescribed by the RC3 linux patch readme, at:
    https://github.com/NetSys/rc3-linux'''

    settings = ['net.ipv4.tcp_dsack=0',
                'net.ipv4.tcp_fack=0',
                'net.ipv4.tcp_timestamps=0',
                'net.core.wmem_max=2048000000',
                "net.ipv4.tcp_wmem='10240 2048000000 2048000000'",
                'net.core.rmem_max=2048000000',
                "net.ipv4.tcp_rmem='10240 2048000000 2048000000'"];
    for setting in settings:
        subprocess.call("sysctl -w %s" % (setting,), shell=True)

def rc3Test(configs):
    ''' Run a test of flow completion times according to config.

    Args:
      configs: A dictionary with the following keys:
        'tcp_type': The tcp algorithm to use, i.e. 'reno' or 'cubic'.
        'bandwidth': The speed of the links in Mbps.
        'delay': The delay to use at each host egress, such as '100ms'
        'time_scale_factor': Amount to scale down flow completion times due
             to delay/rate scaling. E.g. if rate is scaled down by 100, and
             delay is scaled up by 100, then time_scale_factor = 1.0/100.0
        'flows_per_test': Number of times to do a flow completion test
             for each flow length.
        'starter_data_function': A function which returns plot data to augment
             with the test results. See figure15_helpers.py
        'fig_file_name': Name to use for plot output file.
        'fct_offset': Offset time (in post-scaling units) to adjust for
             difference in measuring technique.
    '''
    setupNetVariables()

    topo = RC3Topo(100) # Rate will be overridden by qdiscs
    net = Mininet(topo, link=TCLink)
    net.start()

    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2, s1 = net.getNodeByName('h1', 'h2', 's1')

    # Do test under each configuration.
    for config in configs:
        tcp_type = config['tcp_type']
        bandwidth = config['bandwidth']
        delay = config['delay']
        time_scale_factor = config['time_scale_factor']
        flows_per_test = config['flows_per_test']
        starter_data_function = config['starter_data_function']
        fig_file_name = config['fig_file_name']
        fct_offset = config['fct_offset']

        # Set congestion control default
        print "Setting tcp congestion control algorithm to", tcp_type
        p = Popen("sysctl -w net.ipv4.tcp_congestion_control=%s" \
                  % (tcp_type,), stdout=PIPE, shell=True)
        out, err = p.communicate()
        if (err):
            print "Error:"
            print err
            net.stop()
            exit(1)
        else:
            print out

        print "Configuring qdiscs"
        addPrioQdisc(h1, 'h1-eth0', bandwidth=bandwidth, delay=delay)
        addPrioQdisc(h2, 'h2-eth0', bandwidth=bandwidth, delay=delay)
        addPrioQdisc(s1, 's1-eth1', bandwidth=bandwidth) # No delay
        addPrioQdisc(s1, 's1-eth2', bandwidth=bandwidth) # No delay

        do_fct_tests(net, flows_per_test, time_scale_factor=time_scale_factor,
                     starter_data_function = starter_data_function,
                     fig_file_name = fig_file_name, fct_offset=fct_offset)
    net.stop()

if __name__ == '__main__':
    '''Run prioirty queue correctness tests, and flow completion time tests.'''
    lg.setLogLevel('info')

    # Priority Queue Test - With direct host connections.
    # Run at 100Mbps with 2ms link delay because that appears to be stable
    # and reasonably fast, and use 2ms link delay for faster completion
    # of slow start.
    prioTest(100, '2ms', 1, 60)

    # Priority Queue Test - With switch.
    # Run at 100Mbps with 2ms link delay because that appears to be stable
    # and reasonably fast, and use 2ms link delay for faster completion
    # of slow start.
    prioSwitchTest(100, '2ms', 1, 60)

    # Flow Completion Time Tests
    rc3Test(RC3_fct_test_configs)

