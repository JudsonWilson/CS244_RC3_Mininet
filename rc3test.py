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

DELAY = '1000ms' # 1s

class RC3Topo(Topo):	

    def __init__(self, bandwidth):

        #Initialize Topology
        Topo.__init__(self)

        # Add hosts and switch
        leftHost = self.addHost('h1')
        rightHost = self.addHost('h2')
        switch = self.addSwitch('s1')
        
        # Add links
        self.addLink(leftHost, switch, bw=bandwidth, delay=DELAY, use_htb=True)
        self.addLink(switch, rightHost, bw=bandwidth, delay=DELAY, use_htb=True)

def rc3Test(bandwidth, flowLen):
    topo = RC3Topo(bandwidth)
    net = Mininet(topo, link=TCLink)
    net.start()

    print "Dumping node connections"
    dumpNodeConnections(net.hosts)

if __name__ == '__main__':
    lg.setLogLevel('info')
    rc3Test(LINK_BW_1, 2000)
