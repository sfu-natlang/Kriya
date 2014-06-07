##
## PRO - Implements the Pairwise Ranking Optimization (Hopkins and May, 2011)
## author: bsa33
##

import math
import os.path
import random
import subprocess
import sys
from operator import itemgetter
import time

from MetricScores import *

use_bin_clsfr = True
pairs_2_consider = 5000     # \Gamma in Hopkins and May (2011)
pairs_2_include = 50        # \Xi in Hopkins and May (2011)
clsfr_iters = 100

SAMPLER_TYPE = 'THRESHOLD'
thrhold_percent = 0.02
alpha = 0.05
psi = 0.1

tot_feats = -1
tune_set_size = 0
metricLines = []
sentFVecDict = {}

nbestFile = ""

def generateCandidatePool(sent_indx, cand_hyp_cnt, metricScores):
    global tot_feats
    global pairs_2_consider
    global pairs_2_include
    global sentFVecDict

    sum_g_diffential = 0.0
    hypData = []
    hypVal = []
    hypPairItem = []
    samplePairs = []
    candPairsDict = {}
    if cand_hyp_cnt <= 2: return hypData, hypVal

    featVecLst = sentFVecDict[sent_indx]
    if tot_feats == -1:
        tot_feats = len( featVecLst[0] )

    for l_indx in xrange(pairs_2_consider):
        randTup = tuple( random.sample(xrange(cand_hyp_cnt), 2) )
        if randTup[0] == randTup[1]: continue
        g_diff = math.fabs(metricScores[randTup[0]] - metricScores[randTup[1]])
        if not g_diff: continue
        pairIndxT = randTup if randTup[0] < randTup[1] else (randTup[1], randTup[0])
        if candPairsDict.has_key(pairIndxT): continue
        candPairsDict[pairIndxT] = 1

        sum_g_diffential += g_diff
        hypPairItem.append( g_diff )
        hypPairItem.append( (randTup) )
        samplePairs.append(hypPairItem[:])
        del hypPairItem[:]

    #print "::: ", sent_indx, " :::"
    if (not samplePairs): return hypData, hypVal
    candPool = samplerHelper(sum_g_diffential, samplePairs)
    candPool.sort(key = itemgetter(0), reverse = True)
    sampled_pairs = pairs_2_include if len(candPool) > pairs_2_include else len(candPool)
    for l_indx in xrange(sampled_pairs):
        (curr_g_diff, randTup) = candPool[l_indx]
        #print "  ** ", curr_g_diff

        if use_bin_clsfr:           # Use pair-wise tuning with binary classifier (Hopkins & May, 2011)
            hypVal.append(1)
            hypVal.append(0)
        else:                       # Use pair-wise tuning with linear regression (Bazrafshan, Chung and Gildea, 2012)
            hypVal.append(  math.fabs(metricScores[randTup[0]] - metricScores[randTup[1]]) )
            hypVal.append( -math.fabs(metricScores[randTup[1]] - metricScores[randTup[0]]) )

        hypVec1 = []
        hypVec2 = []
        if ( metricScores[randTup[0]] > metricScores[randTup[1]] ):
            for f_indx in xrange( tot_feats ):
                hypVec1.append(featVecLst[randTup[0]][f_indx] - featVecLst[randTup[1]][f_indx])
                hypVec2.append(featVecLst[randTup[1]][f_indx] - featVecLst[randTup[0]][f_indx])
        else:
            for f_indx in xrange( tot_feats ):
                hypVec1.append(featVecLst[randTup[1]][f_indx] - featVecLst[randTup[0]][f_indx])
                hypVec2.append(featVecLst[randTup[0]][f_indx] - featVecLst[randTup[1]][f_indx])

        hypData.append(hypVec1[:])
        hypData.append(hypVec2[:])
        del hypVec1[:]
        del hypVec2[:]

    return hypData, hypVal

def samplerHelper(sum_g_diffential, samplePairs):
    global SAMPLER_TYPE

    if SAMPLER_TYPE == 'THRESHOLD':
        return naiveSampler(samplePairs)
    elif SAMPLER_TYPE == 'LOGSIGMOID':
        return lSigmoidSampler(sum_g_diffential, samplePairs)

def naiveSampler(samplePairs):
    """ Checks whether the samples should be accepted based on a threshold """

    ## Implements the simpler version suggested in Hopkins and May (2011)
    global alpha
    candPool = []
    for hypPairItem in samplePairs:
        if (hypPairItem[0] > alpha):
            candPool.append( hypPairItem[:] )

    return candPool

def lSigmoidSampler(sum_g_diffential, samplePairs):
    """ Implements the logistic sigmoid sampler """

    candPool = []
    mean_g_differential = sum_g_diffential / len(samplePairs)

    for hypPairItem in samplePairs:
        samp_prob = 1.0 / (1 + math.exp( mean_g_differential - hypPairItem[0] ))
        if getBinomial(1, samp_prob) == 1:
            candPool.append( hypPairItem[:] )

    return candPool

def getBinomial(n, p):
    for i in xrange(n):
        if random.random() < p:
            return 1
    return 0

def loadMetricStats(metScoreFile, metric, start_indx, tot_cands):
    """ Loads metric stats from scores file """

    global metricLines
    metricScores = []

    if not metricLines:
        print "Loading metric stats from file : %s ..." % (metScoreFile)
        msF = open(metScoreFile, 'r')
        for met_line in msF.readlines():
            if metric == 'ter': metricLines.append( max(1.0 - float(met_line), 0.0) )
            else: metricLines.append( float(met_line) )
        msF.close()

    for met_score in metricLines[start_indx:start_indx + tot_cands]:
        metricScores.append( met_score )

    return metricScores

def loadFeatStats(featFile, sent_indx, feat_offset):
    """ Loads the feature stats for all source sentences from features file. """

    global sentFVecDict
    line_cnt = 0
    cands_4_sent = 0
    featLst = []

    if sentFVecDict.has_key(sent_indx):
        return len(sentFVecDict[sent_indx])

    fF = open(featFile, 'r')
    for feat_line in fF:
        line_cnt += 1
        if line_cnt <= feat_offset: continue
        feat_line = feat_line.strip()

        if feat_line.startswith("FEATURES_TXT_BEGIN_0"):
            nbstHeaderLst = feat_line.split()
            src_indx = int(nbstHeaderLst[1])
        elif feat_line.startswith("FEATURES_TXT_END_0"):
            if src_indx < sent_indx: continue
            break
        elif src_indx == sent_indx:
            del featLst[:]
            for x in feat_line.split():
                featLst.append(float(x))
            if not sentFVecDict.has_key(src_indx):
                sentFVecDict[src_indx] = []
            sentFVecDict[src_indx].append( featLst[:] )
            cands_4_sent += 1

    fF.close()
    return cands_4_sent

def metricThresholdLabeler(sent_indx, metricScores):

    global thrhold_percent
    hypVal = []
    thrhold_score = max(metricScores) - (thrhold_percent * max(metricScores))

    tot_neg_points = 0
    for met_score in metricScores:
        if met_score >= thrhold_score: hypVal.append(1)
        else:
            hypVal.append(met_score)
            tot_neg_points += 1

    percent_neg_points = tot_neg_points / float( len(hypVal) )
    if (tot_neg_points == 0 or percent_neg_points <= 0.5):
        sys.stderr.write("Metric Threshold Warning: %d ||| %d :: %d ** %g\n" % (sent_indx, len(hypVal), tot_neg_points, percent_neg_points))

    return hypVal

def setTuningSetSize(featFile):

    global tune_set_size
    src_indx = 0
    fF = open(featFile, 'r')
    for feat_line in fF:
        feat_line = feat_line.strip()
        if feat_line.startswith("FEATURES_TXT_BEGIN_0"):
            nbstHeaderLst = feat_line.split()
            src_indx = int(nbstHeaderLst[1])

    fF.close()
    tune_set_size = src_indx + 1
    sys.stderr.write("Tuning set size : %d\n" % (tune_set_size))

def readInitWgts(wgtsFile):
    wF = open(wgtsFile, 'r');
    w_line = wF.readline()
    wF.close()
    return ( map(lambda x: float(x), w_line.split()) )

def writeFinalWgts(wgtVec, wgtsFile):

    weights = ' '.join( map(lambda x: str('%g' % (x)), wgtVec) )
    wF = open(wgtsFile, 'w');
    wF.write( "%s\n" % (weights) )
    wF.close()

def identifyBestHyps(wgtVec, featFile):

    global tune_set_size
    global sentFVecDict
    sent_indx = 0
    feat_offset = 0
    bestHypIndxLst = []
    for sent_indx in xrange( tune_set_size ):
        #cands_4_sent = loadFeatStats(featFile, sent_indx, feat_offset)
        cands_4_sent = len(sentFVecDict[sent_indx])

        hyp_indx = 0
        best_score = None
        best_hyp = -1
        #featVecLst = sentFVecDict[sent_indx]
        #for hypFeatVec in featVecLst:
        for hypFeatVec in sentFVecDict[sent_indx]:
            i = 0
            hyp_score = 0
            for f_val in hypFeatVec:
                hyp_score += wgtVec[i] * f_val
                i += 1
            if best_score is None or best_score < hyp_score:
                best_score = hyp_score
                best_hyp = hyp_indx
            hyp_indx += 1

        bestHypIndxLst.append(best_hyp)
        feat_offset += cands_4_sent + 2

    return bestHypIndxLst

def linearClassifier(featNames, optFile, workDir):

    megamNewWgtsFile = workDir + 'megam.weights.txt'

    mWF = open(megamNewWgtsFile, 'w')
    megam_scr = os.path.abspath( os.path.dirname(sys.argv[0]) )
    if megam_scr.endswith('/'): megam_scr = megam_scr + 'run_megam.sh'
    else: megam_scr = megam_scr + '/run_megam.sh'
    cmdArgs = ['sh', megam_scr, optFile]
    sys.stderr.write("Executing command: %s\n" % (' '.join( cmdArgs )))
    subprocess.call(cmdArgs, stdout=mWF)
    mWF.close()

    featWgts = []
    tempDict = {}
    mWF = open(megamNewWgtsFile, 'r')
    for wgt_line in mWF:
        wgt_line = wgt_line.strip()
        if not wgt_line.startswith('w_'): continue
        (f_name, f_wgt) = wgt_line.split(' ')
        tempDict[f_name] = float(f_wgt)
    mWF.close()

    for f_name in featNames:
        featWgts.append(tempDict[f_name])

    return featWgts

def svmClassifier(featNames, optFile, workDir):

    modelFile = workDir + 'svmrank.weights.txt'
    svnrank_scr = os.path.abspath( os.path.dirname(sys.argv[0]) )
    if svnrank_scr.endswith('/'): svnrank_scr = svnrank_scr + 'run_svmrank.sh'
    else: svnrank_scr = svnrank_scr + '/run_svmrank.sh'
    cmdArgs = ['sh', svnrank_scr, optFile, modelFile]
    sys.stderr.write("Executing command: %s\n" % (' '.join( cmdArgs )))
    subprocess.call(cmdArgs)

    featWgts = [0.0 for x in featNames]
    mF = open(modelFile, 'r')
    for wgt_line in mF:
        wgt_line = wgt_line.strip()
        if not wgt_line.endswith('#'): continue

        (alpha_w, _) = wgt_line.split(' ', 1)
        alpha_w = float(alpha_w)
        for feat_wgt_pair in wgt_line.split(' '):
            if feat_wgt_pair.find(':') == -1: continue
            (feat, wgt) = feat_wgt_pair.split(':')
            feat_id = int(feat) - 1
            featWgts[feat_id] = alpha_w * float(wgt)
    mF.close()

    return featWgts

def normalizeWgts(unNormWgts):

    sum_wgt = 0.0
    for f_wgt in unNormWgts: sum_wgt += math.fabs(f_wgt)

    newWgts = []
    for f_wgt in unNormWgts:
        newWgts.append( f_wgt/ sum_wgt )
    return newWgts

def interpolateWgts(prevWgts, currWgts):

    global psi

    i = 0
    newWgts = []
    for f_wgt in currWgts:
        new_wgt = (psi * f_wgt) + ((1 - psi) * prevWgts[i])
        newWgts.append( new_wgt )
        i += 1
    return newWgts

def execPRO(run_id, what_metrics, workDir, refFile, metricFiles):

    global metricLines
    global tune_set_size
    global nbestFile
    nbestFile = workDir + "all.nbest.out"
    featFile = workDir + "all.features.dat"
    wgtsFile = workDir + "run" + str(run_id) + ".weights.txt"
    optFile = workDir + 'run' + str(run_id) + '.opt.dat'

    prevWgtVec = readInitWgts(wgtsFile)
    featNames = ['w_lm', 'w_glue', 'w_wp', 'w_tm0', 'w_tm1', 'w_tm2', 'w_tm3', 'w_tm4']
    featsLst = []

    setTuningSetSize(featFile)

    oF = open(optFile, 'w')
    zz = 0
    cont_sent_indx = 0
    for curr_metric in what_metrics.split(':'):
        metricScoreFile = metricFiles[zz]
        metricLines = []
        sent_indx = 0
        start_indx = 0
        feat_offset = 0
        while sent_indx < tune_set_size:
            cands_4_sent = loadFeatStats(featFile, sent_indx, feat_offset)
            metricScores = loadMetricStats(metricScoreFile, curr_metric, start_indx, cands_4_sent)
            if curr_metric == 'pareto' or SAMPLER_TYPE == 'rank':
                hypData = sentFVecDict[sent_indx]
                hypVal = metricScores[:]
            elif SAMPLER_TYPE == 'none':
                hypData = sentFVecDict[sent_indx]
                hypVal = metricThresholdLabeler(sent_indx, metricScores)
            else:
                hypData, hypVal = generateCandidatePool(sent_indx, cands_4_sent, metricScores)

            i = 0
            for featVec in hypData:
                j = 0
                for f_val in featVec:
                    if f_val != 0.0:
                        if curr_metric == 'pareto' or SAMPLER_TYPE == 'rank' or SAMPLER_TYPE == 'none':
                            featsLst.append( str(j+1) + ':' + str(f_val) )
                        else: featsLst.append( featNames[j] + ' ' + str(f_val) )
                    j += 1
                if curr_metric == 'pareto' or SAMPLER_TYPE == 'rank' or SAMPLER_TYPE == 'none':
                    oF.write( "%g qid:%d %s\n" % (hypVal[i], cont_sent_indx+1, ' '.join(featsLst)) )
                else: oF.write( "%d\t%s\n" % (hypVal[i], ' '.join(featsLst)) )
                i += 1
                del featsLst[:]
            sent_indx += 1
            cont_sent_indx += 1
            start_indx += cands_4_sent
            feat_offset += cands_4_sent + 2
        zz += 1

    oF.close()

    if SAMPLER_TYPE == 'rank' or SAMPLER_TYPE == 'none':
        wgtVec = svmClassifier(featNames, optFile, workDir)
    else:
        wgtVec = linearClassifier(featNames, optFile, workDir)

    finalWgts = normalizeWgts( wgtVec )
    newWgtsFile = workDir + "weights.txt"
    writeFinalWgts(finalWgts, newWgtsFile)

    logFile = workDir + "pro.log"
    bestHypIndxLst = identifyBestHyps(finalWgts, featFile)
    eval_met = MetricScores(workDir, refFile, nbestFile, bestHypIndxLst, logFile)

def main():
    global SAMPLER_TYPE

    run_id = int(sys.argv[1])
    workDir = sys.argv[2]
    refFile = sys.argv[3]
    metricFiles = sys.argv[4].split(':')
    if len(sys.argv) >= 6:
        samp_type = sys.argv[5].lower()
        if (not (samp_type == 'threshold' or samp_type == 'logsigmoid' or samp_type == 'none' or samp_type == 'rank')):
            sys.stderr.write("'Sampler type' argument should be Threshold or Logsigmoid\n")
            sys.exit(1)
        elif samp_type == 'threshold': SAMPLER_TYPE = 'THRESHOLD'
        elif samp_type == 'logsigmoid': SAMPLER_TYPE = 'LOGSIGMOID'
        else: SAMPLER_TYPE = samp_type

    if len(sys.argv) == 7:
        what_metrics = sys.argv[6].lower()
        for met in what_metrics.split(':'):
            if (not (met == 'bleu' or met == 'meteor' or met =='ribes' or met == 'ter')):
                sys.stderr.write("Only BLEU, METEOR, RIBES and TER are supported currently as gold metrics\n")
                sys.exit(1)

    if not workDir.endswith("/"): workDir += "/"
    sys.stderr.write("Using %s sampler for sampling candidate pairs\n" % (SAMPLER_TYPE))
    sys.stderr.write("Using %s as gold metrics for optimization\n" % (what_metrics))

    t_beg = time.time()
    execPRO(run_id, what_metrics, workDir, refFile, metricFiles)
    t_end = time.time()
    sys.stderr.write("Total time taken     : %g sec\n" % (t_end - t_beg))

if __name__ == '__main__':
    main()
