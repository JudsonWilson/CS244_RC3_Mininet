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

import matplotlib.pyplot as plt


# Actual experiment was 10Gbps and 1Gbps with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product

LINK_BW_1 = 100 # 100Mbps
LINK_BW_2 = 10 # 10Mbps

#DELAY = '500ms' # 0.5s, RTT=2s
DELAY = '2ms' # TODO remove (test)

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
    node.cmdPrint('tc qdisc del dev', devStr, 'root')
    node.cmdPrint('tc qdisc add dev' ,devStr, 'root handle 1: htb default 1')
    node.cmdPrint('tc class add dev', devStr, 'parent 1: classid 1:1 htb rate 100Mbit ceil 100Mbit')
    node.cmdPrint('tc qdisc add dev', devStr,
            'parent 1:1 handle 2:0 prio bands 8 priomap 0 1 2 3 4 5 6 7 7 7 7 7 7 7 7 7')

    node.cmdPrint('tc filter add dev', devStr, 'parent 2:0 protocol ip prio 10 u32 match ip tos 0x00 0xff flowid 2:1')
    node.cmdPrint('tc filter add dev', devStr, 'parent 2:0 protocol ip prio 10 u32 match ip tos 0x04 0xff flowid 2:2')
    node.cmdPrint('tc filter add dev', devStr, 'parent 2:0 protocol ip prio 10 u32 match ip tos 0x08 0xff flowid 2:3')
    node.cmdPrint('tc filter add dev', devStr, 'parent 2:0 protocol ip prio 10 u32 match ip tos 0x0c 0xff flowid 2:4')
    node.cmdPrint('tc filter add dev', devStr, 'parent 2:0 protocol ip prio 10 u32 match ip tos 0x10 0xff flowid 2:5')

    #node.cmdPrint('ifconfig', devStr, 'txqueuelen 150')

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

    net.stop()

def prioTest(bandwidth, interval, duration):
    topo = RC3Topo(bandwidth)
    net = Mininet(topo, link=TCLink)
    net.start()

    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2 = net.getNodeByName('h1', 'h2')

    print "Adding qdiscs"
    addPrioQdisc(h1, 'h1-eth0')
    addPrioQdisc(h2, 'h2-eth0')

    h1.cmd('killall iperf3')
    h2.cmd('killall iperf3')

    print "Testing bandwidth with high and low priority flows..."
    h2.popen('iperf3 -s -p 5001 -i 1 > servhi.log 2> servhi.log', shell=True) #high
    h2.popen('iperf3 -s -p 5002 -i 1 > servlo.log 2> servlo.log', shell=True) #low

    popens = {}
    print 'launching high priority iperf'
    popens['hiperf'] = h1.popen('iperf3 -c %s -p 5001 -i %d -t %d -S 0x0  > outhi.csv' % 
            (h2.IP(), interval, duration), shell=True)

    sleep(5)

    print 'launching low priority iperf'
    popens['loperf'] = h1.popen('iperf3 -c %s -p 5002 -i %d -t %d -S 0x4 > outlo.csv' % 
            (h2.IP(), interval, duration), shell=True)

    times = duration
    while times > 0:
        h1.cmdPrint('tc -s class ls dev h1-eth0')
        sleep(1)
        times -= 1

    popens['hiperf'].wait()
    print 'high priority finished'

    popens['loperf'].wait()
    print 'low priority finished'

    net.stop()


if __name__ == '__main__':
    lg.setLogLevel('info')
    #rc3Test(37, 20000)
    prioTest(LINK_BW_1, 1, 20)

    plt.plot([1,2,3,4])
    plt.ylabel('some numbers')
   # plt.show()
