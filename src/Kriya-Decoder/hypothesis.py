## @author baskaran

import sys

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

    @classmethod
    def createFromRule(cls, r_item, span):
        return Hypothesis(r_item.score, r_item.src, r_item.tgt, StatefulFeatures.initNew(r_item.lm_heu), \
                          0, span, r_item, (), [ConsequentItem(r_item.tgt.split())])

    def getScoreSansLmHeu(self):
        return self.score - self.sf_feat.lm_heu

    def getScoreSansLM(self):
        #return self.score - (self.sf_feat.lm_heu + self.sf_feat.comp_score)
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

        tgtWrds = self.tgt.split()
        if tgtWrds[0] == "<s>" and tgtWrds[-1] == "</s>":
            return ' '.join(tgtWrds[1:-1])
        elif tgtWrds[0] == "<s>" and not tgtWrds[-1] == "</s>":
            return ' '.join(tgtWrds[1:])
        elif not tgtWrds[0] == "<s>" and tgtWrds[-1] == "</s>":
            return ' '.join(tgtWrds[:-1])
        else: return ' '.join(tgtWrds)

    def getFeatVec(self):
        '''Return the feature values of the Hypothesis as a vector'''

        cand_hyp = self.getHypothesis()
        agg_sl_feat, agg_sf_feat = self.computeFeatures()
        feat_str = FeatureManager.formatFeatureVals(cand_hyp, agg_sl_feat, agg_sf_feat)
        return feat_str

    def printEntry(self):
        '''Prints the specific elements of the result'''

        cand_hyp = self.getHypothesis()
        agg_sl_feat, agg_sf_feat = self.computeFeatures()
        feat_str = FeatureManager.formatFeatureVals(cand_hyp, agg_sl_feat, agg_sf_feat)
        return cand_hyp, feat_str

    def computeFeatures(self):
        agg_sl_feat = StatelessFeatures.copySLFeat(self.inf_rule.sl_feat)
        agg_sf_feat = StatefulFeatures.replicateSFFeat(self.sf_feat)
        entryStack = [ent_obj for ent_obj in self.bp]

        while entryStack:
            ent_obj = entryStack.pop(0)
            agg_sl_feat.aggregFeatScore(ent_obj.inf_rule.sl_feat)
            agg_sf_feat.aggregFeatScore(ent_obj.sf_feat)
            for bp_ent_obj in ent_obj.bp:
                entryStack.append(bp_ent_obj)

        return agg_sl_feat, agg_sf_feat

    def printIt(self):
        '''Print the entry (for debugging purposes)'''

        print "Score    :", self.score
        print "LM Heu   :", self.sf_feat.lm_heu
        print "Target   :", self.tgt
        print "Feat-vec :", self.getFeatVec()
        print "Bpointer :", self.bp
