#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import lg
from mininet.link import TCLink
from mininet.util import pmonitor
from time import time
from signal import SIGINT

import matplotlib.pyplot as plt


# Actual experiment was 10Gbps and 1Gbps with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product

LINK_BW_1 = 100 # 100Mbps
LINK_BW_2 = 10 # 10Mbps

#DELAY = '500ms' # 0.5s, RTT=2s
DELAY = '20ms' # TODO remove (test)

class RC3Topo(Topo):	

    def __init__(self, bandwidth):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        switch = self.addSwitch('s1')

        # Add links
        self.addLink(h1, switch, bw=bandwidth, delay=DELAY, use_htb=True)
        self.addLink(switch, h2, bw=bandwidth, delay=DELAY, use_htb=True)


def addPrioQdisc(node, devStr):
    node.cmdPrint('tc qdisc add dev', devStr,
            'parent 10:1 handle 15:0 prio bands 8 priomap 0 1 2 3 4 5 6 7 7 7 7 7 7 7 7 7')
    node.cmdPrint('tc filter add dev', devStr, 'parent 15:0 protocol ip prio 10 u32 match ip tos 0x00 0xff flowid 15:1')
    node.cmdPrint('tc filter add dev', devStr, 'parent 15:0 protocol ip prio 10 u32 match ip tos 0x04 0xff flowid 15:2')
    node.cmdPrint('tc filter add dev', devStr, 'parent 15:0 protocol ip prio 10 u32 match ip tos 0x08 0xff flowid 15:3')
    node.cmdPrint('tc filter add dev', devStr, 'parent 15:0 protocol ip prio 10 u32 match ip tos 0x0c 0xff flowid 15:4')
    node.cmdPrint('tc filter add dev', devStr, 'parent 15:0 protocol ip prio 10 u32 match ip tos 0x10 0xff flowid 15:5')

    node.cmdPrint('tc qdisc show')
    node.cmdPrint('tc class show dev', devStr)
    node.cmdPrint('tc filter show dev', devStr)

def rc3Test(bandwidth, flowLen):
    topo = RC3Topo(bandwidth)
    net = Mininet(topo, link=TCLink)
    net.start()


    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2 = net.getNodeByName('h1', 'h2')

    print "Adding qdiscs"
    addPrioQdisc(h1, 'h1-eth0')
    addPrioQdisc(h2, 'h2-eth0')
    #TODO do we need this at the switch too?

    print "Testing bandwidth between 'h1' and 'h2'"
    h2.sendCmd('iperf -s')
    #result = h1.cmd('iperf -c', h2.IP(), '-n', flowLen)
    #print result

    popens = {}
    print 'launching high priority iperf'
    popens['hiperf'] = h1.popen('iperf -c %s -n %i -S 0x0 > hiperf.txt' % (h2.IP(), flowLen))
    print 'launching low priority iperf'
    popens['loperf'] = h1.popen('iperf -c %s -n %i -S 0x4 > loperf.txt' % (h2.IP(), flowLen))

    '''
    endTime = time() + 40 #seconds
    for perf, line in pmonitor(popens, timeoutms=1000):
        h1.cmdPrint('tc -s class ls dev h1-eth0')
        if perf:
            print '<%s>: %s' % (perf, line)
        if time() >= endTime:
            print 'timeout'
            for p in popens.values():
                p.send_signal( SIGINT )
    '''

    #TODO redirect iperf to files
    #TODO parse files
    #TODO display graph

    net.stop()

if __name__ == '__main__':
    lg.setLogLevel('info')
    rc3Test(37, 20000)

    plt.plot([1,2,3,4])
    plt.ylabel('some numbers')
    plt.show()
