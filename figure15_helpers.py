#!/usr/bin/env python
# a bar plot with errorbars
import numpy as np
import matplotlib.pyplot as plt

def avg(s):
    '''Compute average of list or string of values. From CS244 lab 2.'''
    if ',' in s:
        lst = [float(f) for f in s.split(',')]
    elif type(s) == str:
        lst = [float(s)]
    elif type(s) == list:
        lst = s
    return sum(lst)/len(lst)

def stddev(s):
    '''Compute stddev of list or string of values. Adapted from avg().'''
    if ',' in s:
        lst = [float(f) for f in s.split(',')]
    elif type(s) == str:
        lst = [float(s)]
    elif type(s) == list:
        lst = s

    return np.std(lst)

def figure15a_paper_data():
    '''Populate data struct for plot, using data from figure 15a in paper.

    For plotBarClusters() below. Fill in "Mininet ..." fields with test data.

    Extracted manually from paper using this tool:
    http://arohatgi.info/WebPlotDigitizer/app/
    '''

    flow_completion_times = [1460, 7300, 14600, 73000, 146000, 730000, 1460000]

    data = {
        1460    :{'Simulated Regular TCP':{'mean':0.0296,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0296,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.0296,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                  'Real RC3'             :{'mean':0.0296,'stddev':0.00022},
                 },
        7300    :{'Simulated Regular TCP':{'mean':0.0296,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0296,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.0296,'stddev':0.00022},
                  'Real RC3'             :{'mean':0.0296,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                 },
        14600   :{'Simulated Regular TCP':{'mean':0.0296,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0296,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.0300,'stddev':0.00022},
                  'Real RC3'             :{'mean':0.0300,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                  },
        73000   :{'Simulated Regular TCP':{'mean':0.0698,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0298,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.0702,'stddev':0.00022},
                  'Real RC3'             :{'mean':0.0302,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                 },
        146000  :{'Simulated Regular TCP':{'mean':0.0897,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0298,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.0909,'stddev':0.000345},
                  'Real RC3'             :{'mean':0.0307,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                 },
        730000  :{'Simulated Regular TCP':{'mean':0.1306,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0302,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.1746,'stddev':0.00202},
                  'Real RC3'             :{'mean':0.0356,'stddev':0.00022},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                 },
        1460000 :{'Simulated Regular TCP':{'mean':0.1513,'stddev':0},
                  'Simulated RC3'        :{'mean':0.0307,'stddev':0},
                  'Real Regular TCP'     :{'mean':0.2184,'stddev':0.00505},
                  'Real RC3'             :{'mean':0.0453,'stddev':0.00180},
                  'Mininet Regular TCP'  :{'mean':0,'stddev':0}, #dummy
                  'Mininet RC3'          :{'mean':0,'stddev':0}, #dummy
                 },
    }

    flow_types = ['Simulated Regular TCP',
                  'Simulated RC3',
                  'Real Regular TCP',
                  'Real RC3',
                  'Mininet Regular TCP',
                  'Mininet RC3']


    flow_type_colors = {'Simulated Regular TCP':'#990000',
                        'Simulated RC3':'#999999',
                        'Real Regular TCP':'#0066cc',
                        'Real RC3':'#ffa700',
                        'Mininet Regular TCP':'#0e9a0a',
                        'Mininet RC3':'k'}

    return (data, flow_types, flow_type_colors, "Figure 15(a)")

def plotBarClusers(plot_data, flow_types, flow_type_colors, title="",
                   fig_file_name = None):
    '''Make a bar chart plot of organized plot_data.

    Designed in the style of figure 15 of paper Mittal, et. al. "Recursively
    Cautious Congestion Control," 2014.

    The bars are of height "mean" and error bars for "stddev".
    The x-axis is arranged by flow_length, and for each flow_length
    a group of bars is made, representing each flow type (Simulated TCP,
    Real RC3, etc.)

    plot_data: The data to plot. A parent dictionary which has keys which are
        the flow lengths. For each flow length, there is a dictionary with the
        data for each flow type, which is a dictionary of the
        'mean' and 'stddev'. E.g., for just a single flow length of 1460:

        plot_data = {1460:{'Real RC3':{'mean':1234,'stddev':50},
                           'Mininet RC3':{'mean':1200,'stddev':100},
                           ...
                          }
                    }
    flow_types: A list of flow types, e.g. 'Real RC3' or 'Simulated RC3',
        and the bars / legend appear in the order of this list.
    flow_type_colors: maps flow type string to a color for the bars of same
        flow type and their legend entry.
    title: Title to print on the graph.
    fig_file_name: If not None, will save as file with this name.
    '''

    flow_lens = sorted(plot_data.keys())

    fig, ax = plt.subplots()

    width = 0.9/len(flow_types) # Bar width. 0.9 makes space between groups.

    type_count = 0 #which flow type we are on. Used for bar-placement by type
    rects = ()
    rect_labels = ()
    for flow_type in flow_types:
        ind_count = 0
        ind = np.array([])
        means = []
        stddevs = []
        for flow_len in flow_lens:
            # Add bar if there is one of this type for this flow len
            if flow_type in plot_data[flow_len]:
                ind = np.append(ind, ind_count)
                means.append(plot_data[flow_len][flow_type]['mean'])
                stddevs.append(plot_data[flow_len][flow_type]['stddev'])
            ind_count += 1;

        # Draw bars for this flow type. Save rects/labels for legend.
        rects += (ax.bar(ind+width*type_count, means, width,
                         color=flow_type_colors[flow_type], yerr=stddevs),)
        rect_labels += (flow_type,)

        type_count += 1

    # add some text for labels, title and axes ticks
    ax.set_ylabel('Average FCT (secs)')
    ax.set_title(title)
    ind = np.array(range(len(flow_lens)))
    ax.set_xticks(ind+width*len(flow_types)/2)
    ax.set_xticklabels( flow_lens )
    ax.set_xlabel('Flow Size (bytes)')

    ax.legend(rects, rect_labels, loc='best')

    if fig_file_name is not None:
      plt.savefig(fig_file_name)

    plt.show()

if __name__ == "__main__":
    '''Debug mode function to test code above.'''
    (data, flow_types, flow_type_colors, title) = figure15a_paper_data()
    plotBarClusers(data, flow_types, flow_type_colors, title)


