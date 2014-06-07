import sys
import time
from optparse import OptionParser

thrhold_percent = 0.02
indicator_bits = ''
metScrFiles = []
origMetricScores = []
scoresLst = []
metricsLst = []
nBestLines = []
scoresLines = []
indxSentDict = {}

def loadNbestHypotheses(nBestFile, sent_indx, offset):
    """ Loads the feature stats for all source sentences from features file. """

    global nBestLines
    global indxSentDict
    sent_id = -1
    line_id = 0
    cand_id = 0
    indxSentDict.clear()

    if not nBestLines:
        nBF = open(nBestFile, 'r')
        nBestLines = nBF.readlines()
        nBF.close()

    for line in nBestLines[offset:]:
        line = line.strip()
        (sent_id, cand_hyp, _) = line.split('||| ', 2)
        sent_id = int(sent_id)
        if sent_id > sent_indx: break

        if sent_id == sent_indx:
            indxSentDict[cand_id] = cand_hyp
            cand_id += 1

    return sent_id, cand_id

def loadMetricScores(offset, cands):

    global metScrFiles
    global indicator_bits
    global origMetricScores
    global scoresLines
    global scoresLst
    global metricsLst
    del origMetricScores[:]
    del scoresLst[:]
    del metricsLst[:]

    if not scoresLines:
        for met_indx in xrange( len(metScrFiles) ):
            mF = open(metScrFiles[met_indx], 'r') 
            scoresLines += [ mF.readlines() ]
            mF.close()

    for met_indx in xrange( len(metScrFiles) ):
        if indicator_bits[met_indx] == '1': error_metric = True
        else: error_metric = False

        cand_id = 0
        for line in scoresLines[met_indx][offset:offset+cands]:
            if error_metric: met_score = max(1.0 - float(line), 0)
            else: met_score = float(line)
            if met_indx == 0:
                scoresLst.append( (cand_id, met_score,) )
            else:
                tempLst = list( scoresLst[cand_id] )
                tempLst.append(met_score)
                scoresLst[cand_id] = tuple(tempLst)
            cand_id += 1

    origMetricScores = scoresLst[:]         # copy the original metric scores
    scoresLst.sort( cmp = metricComparator )
    pruneNonParetoPoints()
    metricsLst = scoresLst[:]

def metricComparator(hyp1, hyp2):
    return cmp(hyp1[1:], hyp2[1:])

def pruneNonParetoPoints():
    """ Prunes the metric scores list to remove the non-pareto points (speeds up pareto frontier identification) """

    global scoresLst
    betterHyp = scoresLst[-1]

    tot_points = len(scoresLst)
    for h_indx in xrange( tot_points-2, -1, -1 ):
        currHyp = scoresLst[h_indx]
        if isHyp1StrictlyBetter(betterHyp, currHyp):
            scoresLst.pop(h_indx)
            continue
        betterHyp = currHyp

def isHyp1StrictlyBetter(hyp1, hyp2):

    for met_indx in xrange(1, len(hyp1)):
        if not hyp1[met_indx] > hyp2[met_indx]: return False

    return True

def findParetoPoints():

    global scoresLst
    paretoPoints = []

    while scoresLst:
        paretoHyp = scoresLst.pop()
        for h_indx in xrange(len(scoresLst)-1, -1, -1):
            currHyp = scoresLst[h_indx]
            if isHyp1Dominates(paretoHyp, currHyp):
                scoresLst.pop(h_indx)
            elif isHyp1Dominates(currHyp, paretoHyp):
                paretoHyp = currHyp
                scoresLst.pop(h_indx)
        paretoPoints.append(paretoHyp)

        for h_indx in xrange(len(scoresLst)-1, -1, -1):
            currHyp = scoresLst[h_indx]
            if isHyp1Dominates(paretoHyp, currHyp):
                scoresLst.pop(h_indx)

    return paretoPoints

def isHyp1Dominates(hyp1, hyp2):

    for met_indx in xrange(1, len(hyp1)):
        if hyp1[met_indx] > hyp2[met_indx]:
            if isHyp1NotWorse(met_indx, hyp1, hyp2):
                return True

    return False

def isHyp1NotWorse(fix_met_indx, hyp1, hyp2):
    """ Checks hyp1 is *at least* as good as hyp2 for all but one metric """

    # For a fixed metric-index 'm': hyp1 was found to be strictly better i.e. hyp1[m] > hyp2[m]
    # This functions checkts if hyp1 is at least as good as hyp2 in other metrics
    # if: (hyp1[n] >= hyp2[n]) for all (n != m), return True
    # else: return False
    for met_indx in xrange(1, len(hyp1)):
        if met_indx != fix_met_indx:
            if not hyp1[met_indx] >= hyp2[met_indx]: return False

    return True

def printParetoCands(sent_indx, paretoPoints, metricWgts, outFile, clsfrFile, incl_lc_positives):

    global thrhold_percent
    global indxSentDict
    global origMetricScores
    global metricsLst
    paretoIndxDict = {}
    with open(outFile, 'a') as oF:
        paretoPoints.sort()
        for p_point in paretoPoints:
            p_indx = p_point[0]
            paretoIndxDict[p_indx] = 1
            for hyp in metricsLst:
                if hyp[0] == p_indx:
                    met_scores = ' '.join([str(x) for x in hyp[1:]])
                    #oF.write("%d ||| %d ||| %s\n" % (sent_indx, p_indx, indxSentDict[p_indx].strip()))
                    oF.write("%d ||| %d ||| %s ||| %s\n" % (sent_indx, p_indx, indxSentDict[p_indx].strip(), met_scores))
                    break

    if clsfrFile is None: return None

    metricScores = []
    tot_metrics = float(len( metricWgts ))
    for c_indx in xrange( len(indxSentDict.keys()) ):
        i = 0
        wgt_sum = 0.0
        for met_score in origMetricScores[c_indx][1:]:
            wgt_sum += (met_score * metricWgts[i])
            i += 1
        metricScores.append( wgt_sum/ tot_metrics )
    thrhold_score = max(metricScores) - (thrhold_percent * max(metricScores))

    with open(clsfrFile, 'a') as cF:
        for c_indx in xrange( len(indxSentDict.keys()) ):
            if (paretoIndxDict.has_key(c_indx) or \
                (incl_lc_positives and metricScores[c_indx] >= thrhold_score)):
                label = 1
            else: label = metricScores[c_indx]
            cF.write("%g\n" % (label))

def identifyParetoHypotheses(nBestFile, metricWgts, outFile, clsfrFile, incl_lc_positives=False):

    global indxSentDict
    global scoresLst
    offset = 0
    sent_id = 0
    tot_cands = 0
    tot_sents = 0
    sent_offset = 0
    tot_pareto_points = 0
    tot_percent_points = 0
    while True:
        last_sent_seen, cands_in_sent = loadNbestHypotheses(nBestFile, sent_id, offset)
        offset += cands_in_sent
        if last_sent_seen == -1: break

        curr_cands = len(indxSentDict.keys())
        loadMetricScores(sent_offset, curr_cands)

        paretoPoints = findParetoPoints()
        printParetoCands(sent_id, paretoPoints, metricWgts, outFile, clsfrFile, incl_lc_positives)
        percent_points = len(paretoPoints) / float(curr_cands)
        #sys.stdout.write("Sent# %d ||| %d ||| %d ||| %g\n" % (sent_id, curr_cands, len(paretoPoints), percent_points))

        sent_id += 1
        sent_offset += curr_cands
        tot_cands += curr_cands
        tot_percent_points += percent_points

        if curr_cands > 1:
            tot_sents += 1
            tot_pareto_points += len(paretoPoints)

    sys.stdout.write("** Pareto stats for sentences having more than one N-best candidate **\n")
    sys.stdout.write("Total n-best candidates       : %d\n" % (tot_cands))
    sys.stdout.write("Total sentences in the set    : %d\n" % (tot_sents))
    sys.stdout.write("Total pareto points           : %d\n" % (tot_pareto_points))
    sys.stdout.write("Average # of pareto points    : %g\n" % (float(tot_pareto_points)/ tot_sents))
    sys.stdout.write("Average n-best size           : %g\n" % (tot_cands/ float(sent_id)))
    sys.stdout.write("Average ratio                 : %g\n" % (tot_percent_points/ sent_id))

def trackMetFilesOrder(option, opt_str, value, parser):
    global metScrFiles
    global indicator_bits

    metScrFiles.append(value)
    if (opt_str == '--acc' or opt_str == '-a'): indicator_bits += '0'
    elif (opt_str == '--err' or opt_str == '-e'): indicator_bits += '1'

def main():

    global metScrFiles
    optparser = OptionParser("usage: %prog options (all options are required unless marked optional)")

    optparser.add_option("-n", "--nbest", dest="nBestFile", type="string", help="n-best file", metavar="FILE")
    optparser.add_option("-a", "--acc", action="callback", callback=trackMetFilesOrder, type="string", help="Accuracy metric scores (to be maximized) file", metavar="FILE")
    optparser.add_option("-e", "--err", action="callback", callback=trackMetFilesOrder, type="string", help="Error metric scores (to be minimized) file", metavar="FILE")
    optparser.add_option("-o", "--out", dest="outFile", type="string", help="pareto out file", metavar="FILE")
    optparser.add_option("-c", "--cls", dest="clsfrOutFile", default=None, type="string", help="classifier out file (optional)", metavar="FILE")
    optparser.add_option("-w", "--comb-wgts", dest="comb_wgts", default='0.5:0.5', type="string", help="combination weights (colon separated); should match the order of --acc --err options above")
    optparser.add_option("-l", "--incl-lc-pos", dest="incl_lc_positives", default=False, action="store_true", help="include high scoring lin-comb points as positives along with pareto")

    (opts, args) = optparser.parse_args()
    assert opts.nBestFile is not None, "N-best file from the decoder is required. Exiting!!\n"
    assert opts.outFile is not None, "Specify the output file for the pareto points. Exiting!!\n"
    assert len(metScrFiles) >= 2, "At least two (accuracy or error) metric files must be specified. Exiting!!\n"

    metricWgts = [float(x) for x in opts.comb_wgts.split(':')]
    assert len(metScrFiles) == len(metricWgts), "# of metric score files (%d) is not the same as the # of metric weights (%d)\n" % (len(metScrFiles), len(metricWgts))

    t_beg = time.time()
    identifyParetoHypotheses(opts.nBestFile, metricWgts, opts.outFile, opts.clsfrOutFile, opts.incl_lc_positives)
    tot_time = time.time() - t_beg
    sys.stdout.write("Time taken for finding Pareto frontier : %g\n\n" % (tot_time))

if __name__ == '__main__':
    main()

