#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.util import dumpNodeConnections
from mininet.log import lg
from mininet.link import TCLink

# Actual experiment was 10Gbps and 1Gbps with an RTT of 20ms.
# We reduce the link speed and increase the latency to maintain
# the same Bandwidth-Delay Product

LINK_BW_1 = 100 # 100Mbps
LINK_BW_2 = 10 # 10Mbps

DELAY = '500ms' # 0.5s, RTT=2s

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


def rc3Test(bandwidth, flowLen):
    topo = RC3Topo(bandwidth)
    net = Mininet(topo, link=TCLink)
    net.start()


    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

    h1, h2 = net.getNodeByName('h1', 'h2')

    #add prio qdisc to hosts
    print "Adding qdisc"
    h1.cmdPrint('tc qdisc add dev h1-eth0 parent 10:1 handle 15:0 prio bands 8')
    h1.cmdPrint('tc qdisc show')
    h2.cmdPrint('tc qdisc add dev h2-eth0 parent 10:1 handle 15:0 prio bands 8')
    h2.cmdPrint('tc qdisc show')

    print "Testing bandwidth between 'h1' and 'h2'"
    h2.sendCmd('iperf -s')
    result = h1.cmd('iperf -c', h2.IP(), '-n', flowLen)
    print result
    net.stop()

if __name__ == '__main__':
    lg.setLogLevel('info')
    rc3Test(LINK_BW_1, 20000000)
