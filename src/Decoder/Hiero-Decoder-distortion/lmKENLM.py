## @author baskaran

import os
import sys

kenlm_swig_wrapper = "/home/msiahban/Modules/NGRAM-SWIG-KENLM"
#kenlm_swig_wrapper = os.environ.get("NGRAM_SWIG_KENLM")
if ( kenlm_swig_wrapper is None ):
    sys.stderr.write("Error: Environment variable NGRAM_SWIG_KENLM is not set. Exiting!!\n")
    sys.exit(1)
sys.path.insert(1, kenlm_swig_wrapper)
import settings
from kenlm import *

class KENLangModel(object):
    '''Language Model class for KENLM'''

    LM = None                                       # Class attribute containing LM
    lm_order = None                                 # Class attribute for lm_order
    log_normalizer = 0.434294                       # Normalizer to convert the log-10 value (of KenLM) to natural log
    elider = ''

    __slots__ = ()

    def __init__(self, lm_order, lmFile, elider_str):
        '''Import the KENLM wrapper module and initialize LM'''

        KENLangModel.lm_order = lm_order
        KENLangModel.elider = elider_str
        self.loadLM(lmFile)

    def __del__(self):
        '''Deletes the LM variable'''

        deleteLM(KENLangModel.LM)

    def loadLM(self, lmFile):
        '''Function for loading the LM'''

        KENLangModel.LM = readLM(lmFile)             # Read lmFile into LM variable

    ## Functions for querying the LM
    ## Define them as classmethods so that they can be called directly with class
    @classmethod
    def queryLM(cls, phr, phr_len):
        '''Score a target phrase with the Language Model and return natural log'''

        return KENLangModel.queryLMlog10(phr, phr_len) / cls.log_normalizer

    @classmethod
    def queryLMlog10(cls, phr, phr_len):
        '''Score a target phrase with the Language Model and return base-10 log'''

        return getNGramProb(cls.LM, phr, phr_len)

    @classmethod
    def calcUNKLMScore(cls, sent):
        '''Calculate the LM score contribution by UNK (OOV) words'''

        return scoreUNK(cls.LM, sent) / cls.log_normalizer

    @classmethod
    def printState(cls, state):
        """  Printing the KENLM state object (for debugging) """

        return getHistory(cls.LM, state)

    @classmethod
    def scorePhrnElide(cls, wordsLst, e_len, mgramSpans, statesLst, r_lm_state):
        '''Score all the complete m-grams in a given consequent item'''

        lm_temp = 0.0
        ## Get the forward looking state for current target hypothesis
        if not settings.opts.no_lm_state and r_lm_state is None:
            r_lm_state = getEmptyState(cls.LM)
            dummy_prob = getNGramProb(cls.LM, ' '.join( wordsLst[e_len-cls.lm_order:] ), getEmptyState(cls.LM), r_lm_state)

        ## Score the complete n-gram phraes
        span_indx = 0
        for (mgram_beg, mgram_end) in mgramSpans:
            lm_hist = statesLst[span_indx]
            if lm_hist is None:
                lm_temp += getNGramProb(cls.LM, ' '.join( wordsLst[mgram_beg:mgram_end] ), cls.lm_order, 'true')
            else:
                lm_temp += getNGramProb(cls.LM, ' '.join( wordsLst[mgram_beg:mgram_end] ), lm_hist, 'true')
            span_indx += 1

        # Finally, elide the string again
        e_tgt = ' '.join(wordsLst[0:cls.lm_order-1] + [cls.elider] + wordsLst[e_len-(cls.lm_order-1):])

        return (lm_temp / cls.log_normalizer, e_tgt, r_lm_state)

    @classmethod
    def getLMHeuCost(cls, e_tgt, wordsLst, e_len):
        """ Compute Heuristic LM score for a given consequent item (by merging one or two antecedents).

            Heuristic LM score is calculated for m-1 words in the beginning and end
            of the candidate. The sentence-boundary markers (<s> and </s>) are first
            appended to the candidate and the heuristic scores are then computed
            separately for three cases, i) no boundary, ii) only left boundary and
            iii) only right boundary. The best (max) score from among the three are
            then returned as the LM heuristic score.
        """

        # Compute LM heuristic score for the first m-1 words
        if (wordsLst[0] == "<s>"):                                  # Hypothesis is an S-rule (is_S_rule is True)
            return getLMHeuProb(cls.LM, ' '.join(wordsLst[1:cls.lm_order-1]), 1, 0) / cls.log_normalizer

        if (e_len >= cls.lm_order):                                 # Hypothesis is *not* an S-rule (is_S_rule is False)
            l_edge = ' '.join(wordsLst[0:cls.lm_order-1])
        else: l_edge = e_tgt

        left_edge_heu = getLeftEdgeHeu(cls.LM, l_edge, 0)
        left_edge_heu_sbeg = getLeftEdgeHeu(cls.LM, l_edge, 1)
        lmHeuLst = [left_edge_heu, left_edge_heu_sbeg, left_edge_heu]

        # Compute LM heuristic score for the last m-1 words
        if wordsLst[-1] != "</s>":
            if e_len < cls.lm_order: phr_beg_indx = 0
            else: phr_beg_indx = e_len - cls.lm_order + 1
            r_edge = ' '.join(wordsLst[phr_beg_indx:])
            right_edge_heu = getRightEdgeHeu(cls.LM, r_edge, 0)
            right_edge_heu_send = getRightEdgeHeu(cls.LM, r_edge, 1)
            lmHeuLst[0] += right_edge_heu
            lmHeuLst[1] += right_edge_heu
            lmHeuLst[2] += right_edge_heu_send

        return max(lmHeuLst) / cls.log_normalizer                           # Return the max value of LM heu
