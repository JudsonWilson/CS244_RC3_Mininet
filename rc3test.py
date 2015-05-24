#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import lg
from mininet.link import TCLink
from mininet.util import pmonitor
from time import time
from signal import SIGINT

# Actual experiment was 10Gbps and 1Gbps with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product

LINK_BW_1 = 100 # 100Mbps
LINK_BW_2 = 10 # 10Mbps

#DELAY = '500ms' # 0.5s, RTT=2s
DELAY = '200ms' # TODO remove (test)

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
            'parent 10:1 handle 15:0 prio bands 8 priomap 0 0 1 0 2 0 3 0 4 0 0 0 0 0 0 0')
    node.cmdPrint('tc qdisc show')

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
    '''
    print 'launching high priority iperf'
    h1.sendCmd('iperf -c', h2.IP(), '-n', flowLen, '-S 0x0 > highperf.txt')
    print 'launching low priority iperf'
    h1.sendCmd('iperf -c', h2.IP(), '-n', flowLen, '-S 0x4 > lowperf.txt')
    print 'lol'
    '''

    popens = {}
    print 'launching high priority iperf'
    popens['hiperf'] = h1.popen('iperf -c %s -n %i -S 0x0 > hiperf.txt' % (h2.IP(), flowLen))
    print 'launching low priority iperf'
    popens['loperf'] = h1.popen('iperf -c %s -n %i -S 0x1 > loperf.txt' % (h2.IP(), flowLen))

    endTime = time() + 40 #seconds
    for perf, line in pmonitor(popens, timeoutms=100):
    #    h1.cmdPrint('tc -s qdisc ls dev h1-eth0')
        if perf:
            print '<%s>: %s' % (perf, line)
        if time() >= endTime:
            print 'timeout'
            for p in popens.values():
                p.send_signal( SIGINT )

    net.stop()

if __name__ == '__main__':
    lg.setLogLevel('info')
    rc3Test(LINK_BW_1, 20000000)
