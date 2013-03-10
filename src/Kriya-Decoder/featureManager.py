import math, sys

from features import StatefulFeatures
from features import StatelessFeatures
from languageModelManager import LanguageModelManager
import settings

class FeatureManager(object):
    '''Weights for the different features in the log-linear model''' 

    lmWgt = []
    tmWgt = []
    glue_wgt = 0.0
    wp_wgt = 0.0
    egivenf_offset = 0
    unkRuleTup = ()
    pp_val = math.log(2.718)

    __slots__ = ()

    @classmethod
    def setFeatureWeights(cls, tot_lm_feats, tot_tm_feats, how_many_tm_feats):
        assert (tot_lm_feats == len(cls.lmWgt)), "Error: Language model param should have %d weights instead of %d" % (tot_lm_feats, len(cls.lmWgt))
        assert (tot_tm_feats == len(cls.tmWgt)), "Error: Translation model param should have %d weights instead of %d" % (tot_tm_feats, len(cls.tmWgt))
        for tmVec in cls.tmWgt:
            assert (how_many_tm_feats == len(tmVec)), "Error: # of TM features (%d) doesn't match TM weights count (%d)" % (how_many_tm_feats, len(tmVec))

        cls.egivenf_offset = 2
        StatefulFeatures.setLMInitLst(tot_lm_feats)
        cls.setUnkRule()
        cls.printWeights()
        LanguageModelManager.setLMInfo(cls.lmWgt)

    @classmethod
    def setUnkRule(cls):
        sl_feat = cls.buildUNKFeats()
        p_score = cls.scorePTEntry(sl_feat)
        cls.unkRuleTup = (p_score, 0.0, sl_feat)

    @classmethod
    def printWeights(cls):
        for tm_indx in xrange( len(cls.tmWgt) ):
            tm_wgts_str = ' '.join( [str(x) for x in cls.tmWgt[tm_indx]] )
            sys.stdout.write( "TM-%d weights   : [%s]\n" % (tm_indx, tm_wgts_str) )
        for lm_indx in xrange( len(cls.lmWgt) ):
            sys.stdout.write( "LM-%d weights   : %g\n" % (lm_indx, cls.lmWgt[lm_indx]) )
        sys.stdout.write( "Word penalty and Glue feature weights   : %g %g\n" % (cls.wp_wgt, cls.glue_wgt) )

    @classmethod
    def buildRuleFeats(cls, probs, term_count):
        '''Create the stateless feature object for a regular rule'''
    
        ## All feature values must be represented as log-probs in base 'e' ##
        ## Any log-prob in base '10' must be converted to base 'e' by dividing it by math.log10(math.exp(1)) ##
        # add the TM features
        tmFeatVec = [float(x) for x in probs.split()]        # Already in base-e log-prob
        tmFeatVec.append(cls.pp_val)                         # Add phrase penalty

        return StatelessFeatures(tmFeatVec, -term_count)

    @classmethod
    def buildGlueFeats(cls, glue_val):
        '''Create the stateless feature object for a glue rule'''

        tmFeatVec = [0.0 for x in xrange(len(cls.tmWgt) * len(cls.tmWgt[0]))]
        return StatelessFeatures(tmFeatVec, 0, glue_val)

    @classmethod
    def buildUNKFeats(cls):
        '''Create the stateless feature object for an UNK rule (used for an OOV word)'''

        tmFeatVec = [0.0 for x in xrange(len(cls.tmWgt) * len(cls.tmWgt[0]))]
        return StatelessFeatures(tmFeatVec, -1)

    @classmethod
    def getScore4TTL(cls, sl_f_obj):
        if len(cls.tmWgt) == 1:
            return sl_f_obj.tmFVec[cls.egivenf_offset]

        p_score = 0.0
        for tm_indx in xrange( len(cls.tmWgt) ):
            tm_offset = tm_indx * len( cls.tmWgt[tm_indx] )
            p_score += (cls.tmWgt[tm_indx][cls.egivenf_offset] * sl_f_obj.tmFVec[tm_offset + cls.egivenf_offset])
        return p_score

    @classmethod
    def turnOffGlue(cls, sl_f_obj):
        sl_f_obj.glue = 0

    @classmethod
    def scorePTEntry(cls, sl_f_obj):
        p_score = 0.0
        for tm_indx in xrange( len(cls.tmWgt) ):
            tm_offset = tm_indx * len( cls.tmWgt[tm_indx] )
            for tm_feat_indx in xrange( len(cls.tmWgt[tm_indx]) ):
                p_score += (cls.tmWgt[tm_indx][tm_feat_indx] * sl_f_obj.tmFVec[tm_offset + tm_feat_indx])

        p_score += (cls.wp_wgt * sl_f_obj.wp) + (cls.glue_wgt * sl_f_obj.glue)

        return p_score

    @classmethod
    def scoreHypothesis(cls, sl_f_obj, sf_f_obj):
        p_score = cls.scorePTEntry(sl_f_obj)

        for lm_indx in xrange( len(cls.lmWgt) ):
            p_score += (cls.lmWgt[lm_indx] * sf_f_obj.lmFVec[lm_indx])

        return p_score

    @classmethod
    def scoreStatefulFeatures(cls, sf_f_obj):
        return sf_f_obj.scoreFeature()

    @classmethod
    def formatFeatureVals(cls, cand_hyp, sl_f_obj, sf_f_obj, only_feat_vals=False):

        tm_str, wp_str, glue_str = sl_f_obj.stringifyMembers()
        lm_str = sf_f_obj.stringifyMembers(cand_hyp)

        if only_feat_vals:
            return ' '.join( [lm_str, glue_str, wp_str, tm_str] )

        if (settings.opts.no_glue_penalty):
            feats = ['lm:', 'wp:', 'tm:']
            if (settings.opts.zmert_nbest):
                feat_str = ' '.join( [lm_str, wp_str, tm_str] )
            else:
                feat_str = ' '.join( map(lambda x,y: x+' '+y, feats, [lm_str, wp_str, tm_str]) )
        else:
            feats = ['lm:', 'glue:', 'wp:', 'tm:']
            if (settings.opts.zmert_nbest):
                feat_str = ' '.join( [lm_str, glue_str, wp_str, tm_str] )
            else:
                feat_str = ' '.join( map(lambda x,y: x+' '+y, feats, [lm_str, glue_str, wp_str, tm_str]) )

        return feat_str
