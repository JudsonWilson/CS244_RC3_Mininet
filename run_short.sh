# Run the test suite, using a reduced number of flows (3) for each flow-
# completion-time test. Save results in a folder with prefix "results-short-"
# and a timestamp suffix.

start=`date`
exptid=`date +%b%d-%H:%M`

results_dir=results-short-$exptid

sudo ./rc3test.py -n 3 -d $results_dir
