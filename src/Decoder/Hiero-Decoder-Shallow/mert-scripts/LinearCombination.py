import sys
import time
from optparse import OptionParser

metricScores = []

def loadMetricScores(indicator_bits, metScrFiles):

    global metricScores
    scoresLst = []

    for met_indx in xrange( len(metScrFiles) ):
        if indicator_bits[met_indx] == '1': error_metric = True
        else: error_metric = False
        del scoresLst[:]

        mF = open(metScrFiles[met_indx], 'r') 
        for met_line in mF.readlines():
            if error_metric: met_score = max(1.0 - float(met_line), 0)
            else: met_score = float(met_line)
            scoresLst.append(met_score)
        mF.close()

        metricScores += [ scoresLst[:] ]
        if met_indx == 0: tot_cands = len(scoresLst)
        else: assert len(metricScores[met_indx]) == tot_cands, "Two of the metric score files have unequal number of lines. Exiting!!\n"

    return tot_cands

def writeLinCombScores(tot_cands, metricWgts, linCombFile):

    global metricScores
    tot_metrics = len( metricWgts )
    with open(linCombFile, 'w') as lF:
        for c_indx in xrange(tot_cands):
            lin_comb = 0.0
            for met_indx in xrange(tot_metrics):
                lin_comb += (metricScores[met_indx][c_indx] * metricWgts[met_indx])
            lF.write("%g\n" % (lin_comb/ float(tot_metrics)))

def main():

    optparser = OptionParser("usage: %prog options (all options are required unless marked optional)")

    optparser.add_option("-a", "--acc", dest="maxMetFiles", default=[], action="append", type="string", help="Accuracy metric scores (to be maximized) file", metavar="FILE")
    optparser.add_option("-e", "--err", dest="minMetFiles", default=[], action="append", type="string", help="Error metric scores (to be minimized) file", metavar="FILE")
    optparser.add_option("-o", "--out", dest="outFile", type="string", help="linear combination out file", metavar="FILE")
    optparser.add_option("-w", "--comb-wgts", dest="comb_wgts", default='0.5:0.5', type="string", help="combination weights (colon separated); should match the order of --acc --err options above")

    (opts, args) = optparser.parse_args()
    assert opts.outFile is not None, "Specify the output file for the linear combination scores. Exiting!!\n"
    assert opts.maxMetFiles or opts.minMetFiles, "Specify at least two (accuracy or error) metric files. Exiting!!\n"

    indicator_bits = ''
    metScrFiles = []
    for met_file in opts.maxMetFiles:
        indicator_bits += '0'
        metScrFiles.append(met_file)

    for met_file in opts.minMetFiles:
        indicator_bits += '1'           # set 1 for error metric
        metScrFiles.append(met_file)
    assert len(metScrFiles) >= 2, "At least two (accuracy or error) metric files must be specified. Exiting!!\n"

    metricWgts = [float(x) for x in opts.comb_wgts.split(':')]
    assert len(metScrFiles) == len(metricWgts), "# of metric score files (%d) is not the same as the # of metric weights (%d)\n" % (len(metScrFiles), len(metricWgts))
    sys.stderr.write("Using linear combination weights : %s\n" % (', '.join([str(x) for x in metricWgts])))

    t_beg = time.time()
    tot_cands = loadMetricScores(indicator_bits, metScrFiles)
    writeLinCombScores(tot_cands, metricWgts, opts.outFile)
    tot_time = time.time() - t_beg
    sys.stdout.write("Time taken for linearly combining metric scores : %g\n\n" % (tot_time))

if __name__ == '__main__':
    main()

