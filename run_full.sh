# Run the test suite, using 10 flows for each flow-completion-time test.
# Save results in a folder with prefix "results-full-" and a timestamp suffix.

start=`date`
exptid=`date +%b%d-%H:%M`

results_dir=results-full-$exptid

sudo ./rc3test.py -n 10 -d $results_dir
