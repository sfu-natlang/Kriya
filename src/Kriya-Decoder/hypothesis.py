## @author baskaran

import sys

import settings
from featureManager import FeatureManager
from features import StatelessFeatures
from features import StatefulFeatures
from languageModelManager import LanguageModelManager as lmm
from languageModelManager import ConsequentItem

class Hypothesis(object):
    '''Individual entries in the cells of the parse triangle/ rules list'''

    __slots__ = "score", "src", "tgt", "sf_feat", "depth_hier", "inf_cell", "inf_rule", "bp", "consItems"
 
    def __init__(self, score, src, tgt, sf_f_obj, rule_depth=0, inf_cell=(), inf_rule=None, bp=(), conseqItems=[]):
        self.score = score
        self.src = src
        self.tgt = tgt
        self.sf_feat = sf_f_obj
        self.depth_hier = rule_depth
        self.inf_cell = inf_cell
        self.inf_rule = inf_rule                            # Rule object for the consequent entry
        self.bp = bp                                        # List of entry objects of the antecedents
        self.consItems = conseqItems[:]

    def recombineEntry(self, hyp_w_LM):
        '''Hypothesis recombination: LM info from an existing hypothesis is copied into a new hypothesis with better score'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        self.depth_hier = hyp_w_LM.depth_hier
        self.inf_cell = hyp_w_LM.inf_cell
        self.consItems = hyp_w_LM.consItems[:]

        lm_score_diff = self.sf_feat.copyNScoreDiff(hyp_w_LM.sf_feat)
        self.score += self.sf_feat.lm_heu + lm_score_diff
        return self.score

    def copyLMInfo(self, hyp_w_LM):
        '''Copy the language model information from an existing hypothesis to a new one with the same target'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        self.depth_hier = hyp_w_LM.depth_hier
        self.consItems = hyp_w_LM.consItems[:]

        lm_score_diff = self.sf_feat.copyNScoreDiff(hyp_w_LM.sf_feat)
        self.score += self.sf_feat.lm_heu + lm_score_diff        
        return self.score

    @classmethod
    def createFromRule(cls, r_item, span):
        return Hypothesis(r_item.score, r_item.src, r_item.tgt, StatefulFeatures.initNew(r_item.lm_heu), \
                          0, span, r_item, (), [ConsequentItem(r_item.tgt)])

    def getScoreSansLmHeu(self):
        return self.score - self.sf_feat.lm_heu

    def getScoreSansLM(self):
        return self.score - self.sf_feat.getStateScore()

    def setInfCell(self, span):
        self.inf_cell = span

    def getInfCell(self):
        return self.inf_cell

    def getInfEntry(self):
        return self.inf_entry

    def getBP(self):
        '''Returns the back-pointer of the current hypothesis'''

        return self.bp

    def getSrc(self):
        return self.src

    def getHypScore(self):
        return self.score

    def getHypothesis(self):
        '''Remove the beginning and end sentence markers in the translation'''

        if self.tgt.startswith("<s>") and self.tgt.endswith("</s>"):
            return self.tgt[4:-5]
        elif self.tgt.startswith("<s>") and not self.tgt.endswith("</s>"):
            return self.tgt[4:]
        elif not self.tgt.startswith("<s>") and self.tgt.endswith("</s>"):
            return self.tgt[:-5]
        else: return self.tgt

    def getFeatVec(self):
        '''Return the feature values of the Hypothesis as a vector'''

        cand_hyp = self.getHypothesis()
        sl_feat = self.compStatelessFeats()
        feat_str = FeatureManager.formatFeatureVals(cand_hyp, sl_feat, self.sf_feat)
        return [ float(x) for x in feat_str.split(' ') ]

    def printEntry(self):
        '''Prints the specific elements of the result'''

        cand_hyp = self.getHypothesis()
        sl_feat = self.compStatelessFeats()
        feat_str = FeatureManager.formatFeatureVals(cand_hyp, sl_feat, self.sf_feat)
        return cand_hyp, feat_str

    def compStatelessFeats(self):
        sl_feat = StatelessFeatures.copySLFeat(self.inf_rule.sl_feat)
        entryStack = [ent_obj for ent_obj in self.bp]
        
        while entryStack:
            ent_obj = entryStack.pop(0)
            sl_feat.aggregFeatScore(ent_obj.inf_rule.sl_feat)
            for bp_ent_obj in ent_obj.bp:
                entryStack.append(bp_ent_obj)

        return sl_feat

    def printIt(self):
        '''Print the entry (for debugging purposes)'''

        print "Score    :", self.score
        print "LM Heu   :", self.sf_feat.lm_heu
        print "Target   :", self.tgt
        print "Feat-vec :", self.getFeatVec()
        print "Bpointer :", self.bp
