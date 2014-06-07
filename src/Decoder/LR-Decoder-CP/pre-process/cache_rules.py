# Caching the rules for a small set of sentences prior to decoding #

import sys

# Global variables
inFile = sys.argv[1]
inRuleFile = sys.argv[2]
outSentDir = sys.argv[3]
outRuleDir = sys.argv[4]
NO_2_DECODE = 10                  # Fixes the number of sentences to be decoded

g_bad_rule_cnt = 0
g_good_rule_cnt = 0
sentLst = []
sentWrdsDoD = {}


def readFile(rF_inFile, rF_sent_begin_index, rF_outFile):
    'Reading sentence file for decoding'

    rF_inF = open(rF_inFile, 'r')
    rF_oF = open(rF_outFile, 'w')
    global sentLst
    global wordInitDict
    print 'Reading sentences from file : %s ...' % rF_inFile

    for rF_sent_index, rF_sent in enumerate( rF_inF ):
        rF_sent_count = rF_sent_index + 1
        if rF_sent_count < rF_sent_begin_index:
            continue
        elif rF_sent_count >= (rF_sent_begin_index + NO_2_DECODE):
            break

        rF_sent = rF_sent.strip()
        sentLst.append(rF_sent)
        rF_oF.write( "%s\n" % (rF_sent) )
        for rF_word in rF_sent.split(' '):
            try:
                sentWrdsDoD[rF_sent_index][rF_word] = 1
            except KeyError:
                sentWrdsDoD[rF_sent_index] = {}
                sentWrdsDoD[rF_sent_index][rF_word] = 1

    rF_inF.close()
    rF_oF.close()
    return None


def readRules(rR_ruleFile, rR_outFile):
    'Reads the filtered rules'

    global g_bad_rule_cnt
    global g_good_rule_cnt
    global sentLst
    rR_prev = ''
    rR_prev_is_good = False

    rR_rF = open(rR_ruleFile, 'r')
    rR_oF = open(rR_outFile, 'w')
    print 'Reading rules from file : %s' % rR_ruleFile
    try:
        for rR_line in rR_rF:
            rR_line = rR_line.strip()
            rR_entries = []
            rR_entries = rR_line.split(' ||| ')

            if rR_entries[0] != rR_prev:
                rR_prev = rR_entries[0]
                rR_prev_is_good = quickCheck(rR_entries[0])

            # Ignore the rule if it is found to be incompatible
            if not rR_prev_is_good:
                g_bad_rule_cnt += 1
                continue

            g_good_rule_cnt += 1
            rR_oF.write( "%s ||| %s ||| %s\n" % (rR_entries[0], rR_entries[1], ' '.join(rR_entries[2:])) )

    finally:
        rR_rF.close()
        rR_oF.close()

    rR_ruleEntries = []
    return None


def quickCheck(src_rule):
    '''Check if the words in the rule are all present in any one sentence in sentLst'''

    for sent_indx in sentWrdsDoD.keys():

        rule_incompatible = False
        for src_wrd in src_rule.split(' '):
            if ( not src_wrd.startswith('X__') ) and ( not sentWrdsDoD[sent_indx].has_key(src_wrd) ):
                rule_incompatible = True
                break

        if not rule_incompatible:
            return True

    return False


def main():
    global inFile
    global inRuleFile
    global outRuleDir
    global outSentDir
    global g_bad_rule_cnt
    global g_good_rule_cnt

    sent_begin_index = int( sys.argv[1] )
    oSentFile = outSentDir + sys.argv[1] + '.out'
    oRuleFile = outRuleDir + sys.argv[1] + '.out'

    readFile(inFile, sent_begin_index, oSentFile)

    # Read and filter rules of the dev/test set to be decoded
    readRules(inRuleFile, oRuleFile)

    print 'Total # of rejected rules: %d' % ( g_bad_rule_cnt )
    print 'Total # of filtered rules: %d\n' % ( g_good_rule_cnt )


if __name__ == "__main__":
    main()
