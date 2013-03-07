## @author baskaran

import os
import sys

srilm_swig_wrapper = os.environ.get("NGRAM_SWIG_SRILM")
if ( srilm_swig_wrapper is None ):
    sys.stderr.write("Error: Environment variable NGRAM_SWIG_SRILM is not set. Exiting!!\n")
    sys.exit(1)
sys.path.insert(1, srilm_swig_wrapper)
from srilm import *

class SRILangModel(object):
    '''Language Model class for SRILM'''

    log_normalizer = 0.434294                       # Normalizer to convert the log-10 value (of SRILM) to natural log

    __slots__ = "LM", "lm_order", "elider"

    def __init__(self, lm_order, lmFile, elider_str):
        '''Import the SRILM wrapper module and initialize LM'''

        self.lm_order = lm_order
        self.LM = initLM(lm_order)                  # Initialize a LM variable (of size lm_order)
        self.elider = elider_str
        self.loadLM(lmFile)

    def __del__(self):
        '''Deletes the LM variable'''

        deleteLM(self.LM)

    def loadLM(self, lmFile):
        '''Function for loading the LM'''

        readLM(self.LM, lmFile)

    ## Functions for querying the LM
    ## Define them as classmethods so that they can be called directly with class
    def queryLM(self, phr, phr_len):
        '''Score a target phrase with the Language Model and return natural log'''

        return getNGramProb(self.LM, phr, phr_len) / SRILangModel.log_normalizer

    def queryLMlog10(self, phr, phr_len):
        '''Score a target phrase with the Language Model and return base-10 log'''

        return getNGramProb(self.LM, phr, phr_len)

    def calcUNKLMScore(self, sent):
        '''Calculate the LM score contribution by UNK (OOV) words'''

        sent_len = len( sent.split() )
        return scoreUNK(self.LM, sent, sent_len) / SRILangModel.log_normalizer

    def scorePhrnElide(self, wordsLst, phr_len, mgramSpans):
        '''Score all the complete m-grams in a given target phrase'''

        lm_temp = 0.0
        for (mgram_beg, mgram_end) in mgramSpans:
            for i in range( mgram_beg, mgram_end - (self.lm_order - 1) ):
                lm_temp += getNGramProb(self.LM, ' '.join( wordsLst[i:i+self.lm_order] ), self.lm_order)

        # Elide the string again
        e_tgt = ' '.join(wordsLst[0:self.lm_order-1] + [self.elider] + wordsLst[phr_len-(self.lm_order-1):])

        return (lm_temp / SRILangModel.log_normalizer, e_tgt)

    def getLMHeuCost(self, wordsLst, phr_len):
        """ Compute Heuristic LM score for a given candidate.

            Heuristic LM score is calculated for m-1 words in the beginning and end
            of the candidate. The sentence-boundary markers (<s> and </s>) are first
            appended to the candidate and the heuristic scores are then computed
            separately for three cases, i) no boundary, ii) only left boundary and
            iii) only right boundary. The best (max) score from among the three are
            then returned as the LM heuristic score.
        """

        lmHueLst = [0.0, 0.0, 0.0]
        if (phr_len < self.lm_order): initWrds = wordsLst
        else: initWrds = wordsLst[0:self.lm_order-1]

        # Compute LM heuristic score for the first m-1 words
        if (wordsLst[0] == "<s>"):
            is_S_rule = True
        else:
            is_S_rule = False
            initWrds = ["<s>"] + initWrds

        part_lm_w_edge = 0.0
        part_lm_wo_edge = 0.0
        for i in range( 1, len(initWrds) ):
            part_lm_w_edge += getNGramProb( self.LM, ' '.join( initWrds[:(i+1)] ), i + 1 )
            if (is_S_rule):
                pass
            else:
                part_lm_wo_edge += getNGramProb( self.LM, ' '.join( initWrds[1:(i+1)] ), i )

        lm_heu_w_edge = part_lm_w_edge / SRILangModel.log_normalizer
        if (is_S_rule):
            lm_heu_wo_edge = lm_heu_w_edge
        else:
            lm_heu_wo_edge = part_lm_wo_edge / SRILangModel.log_normalizer

        lmHueLst[1] += lm_heu_w_edge
        lmHueLst[0] += lm_heu_wo_edge
        lmHueLst[2] += lm_heu_wo_edge

        # Compute LM heuristic score for the last m-1 words
        last_indx = phr_len - 1
        if (not is_S_rule and wordsLst[last_indx] != "</s>"):
            if last_indx <= self.lm_order - 1: phr_beg_indx = 1
            else: phr_beg_indx = last_indx - self.lm_order + 2

            phr_end = ' '.join( wordsLst[phr_beg_indx:] ) + " </s>"
            phr_end_len = last_indx - phr_beg_indx + 2
            lmHueLst[2] += ( getNGramProb( self.LM, phr_end, phr_end_len ) / SRILangModel.log_normalizer )

        return max(lmHueLst)                                        # Return the max value of LM heu
