#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import lg
from mininet.link import TCLink
from mininet.util import pmonitor
from time import time
from time import sleep
from signal import SIGINT

import json
import matplotlib.pyplot as plt


# Actual experiment was 10Gbps and 1Gbps with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product

LINK_BW_1 = 100 # 100Mbps
LINK_BW_2 = 10 # 10Mbps

#DELAY = '500ms' # 0.5s, RTT=2s
DELAY = '2ms' # TODO remove (test)

class RC3PrioSwitchTestTopo(Topo):
    def __init__(self, bandwidth):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        switch = self.addSwitch('s1')

        # Add links
        self.addLink(h1, switch, bw=bandwidth, delay=DELAY, use_htb=True)
        self.addLink(h2, switch, bw=bandwidth, delay=DELAY, use_htb=True)
        self.addLink(switch, h3, bw=bandwidth, delay=DELAY, use_htb=True)


class RC3PrioTopo(Topo):	

    def __init__(self, bandwidth):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Add links
        self.addLink(h1, h2, bw=bandwidth, delay=DELAY, use_htb=True)


def addPrioQdisc(node, devStr, bandwidth, delay=None):
    '''Setup the HTB, prio qdisc, netem, etc.

    node: Network node, e.g. h1, h2, s1
    devStr: Device name string, e.g. 'h1-eth0'
    bandwidth: A number, representing amount of Mbps
    delay: a string, such as 10us, or None for no delay.
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
            node.cmdPrint('tc qdisc add dev %s parent 15:%d handle 15%d:'
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

def runPrioSwitchFlows(bandwidth, interval, duration, loOut, hiOut, loFirst):
    topo = RC3PrioSwitchTestTopo(bandwidth)
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

    popens = {}

    print "Testing bandwidth with high and low priority flows..."
    popens['hiserv'] = h3.popen('iperf3 -s -p 5001 -1 -i %f -J > %s'% (interval, hiOut), shell=True)
    popens['loserv'] = h3.popen('iperf3 -s -p 5002 -1 -i %f -J > %s'% (interval, loOut), shell=True)


    if loFirst:
        print 'launching low priority iperf'
        popens['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' % 
                (h3.IP(), interval, duration+1), shell=True)
    else:
        print 'launching high priority iperf'
        popens['hiperf'] = h2.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0  -J ' % 
                (h3.IP(), interval, duration+1), shell=True)

    sleep(duration/ 2)

    if loFirst:
        print 'launching high priority iperf'
        popens['hiperf'] = h2.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0  -J ' % 
                (h3.IP(), interval, (duration/2)+1), shell=True)
    else:
        print 'launching low priority iperf'
        popens['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' % 
                (h3.IP(), interval, (duration/2)+1), shell=True)

    popens['hiperf'].wait()
    popens['loperf'].wait()
    popens['hiserv'].wait()
    popens['loserv'].wait()
    print 'flows finished'

    net.stop()

def prioSwitchTest(bandwidth, interval, duration):
    runPrioSwitchFlows(bandwidth, interval, duration, 'sservlo1.json', 'sservhi1.json', False)
    runPrioSwitchFlows(bandwidth, interval, duration, 'sservlo2.json', 'sservhi2.json', True)
    iperfPlotJSON('sservlo1.json', 'sservhi1.json', 'sservlo2.json', 'sservhi2.json', 'figure_17.png', duration, 'Correctness of Priority Queueing in the Switch')


'''
parse the JSON output from iperf3 and return two arrays with time offsets and
reported bandwidths
'''
def iperfParseJSON(filename, duration, offset):
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

'''
Plot four json files and output as outfile. lofile1 and hifile1 are the flows
for the first test (low priority starts after high priority) and lofile2 and 
hifile2 are for the second test (high priority starts after low priority).
'''
def iperfPlotJSON(lofile1, hifile1, lofile2, hifile2, outfile,duration, title):
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
    print('plot saved to ',outfile)



def runPrioFlows(bandwidth, interval, duration, loOut, hiOut, loFirst):
    topo = RC3PrioTopo(bandwidth)
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

    popens = {}

    print "Testing bandwidth with high and low priority flows..."
    popens['hiserv'] = h2.popen('iperf3 -s -p 5001 -1 -i %f -J > %s'% (interval, hiOut), shell=True)
    popens['loserv'] = h2.popen('iperf3 -s -p 5002 -1 -i %f -J > %s'% (interval, loOut), shell=True)


    if loFirst:
        print 'launching low priority iperf'
        popens['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' % 
                (h2.IP(), interval, duration+1), shell=True)
    else:
        print 'launching high priority iperf'
        popens['hiperf'] = h1.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0  -J ' % 
                (h2.IP(), interval, duration+1), shell=True)

    sleep(duration/ 2)

    if loFirst:
        print 'launching high priority iperf'
        popens['hiperf'] = h1.popen('iperf3 -c %s -p 5001 -i %f -t %d -S 0x0  -J ' % 
                (h2.IP(), interval, (duration/2)+1), shell=True)
    else:
        print 'launching low priority iperf'
        popens['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %f -t %d -S 0x4 -J' % 
                (h2.IP(), interval, (duration/2)+1), shell=True)

    popens['hiperf'].wait()
    popens['loperf'].wait()
    popens['hiserv'].wait()
    popens['loserv'].wait()
    print 'flows finished'

    net.stop()

def prioTest(bandwidth, interval, duration):
    runPrioFlows(bandwidth, interval, duration, 'servlo1.json', 'servhi1.json', False)
    runPrioFlows(bandwidth, interval, duration, 'servlo2.json', 'servhi2.json', True)
    iperfPlotJSON('servlo1.json', 'servhi1.json', 'servlo2.json', 'servhi2.json', 'figure_16.png', duration, 'Correctness of Priority Queueing in Linux')

if __name__ == '__main__':
    lg.setLogLevel('info')
    prioTest(LINK_BW_1, 1, 60)
    prioSwitchTest(LINK_BW_1, 1, 60)

