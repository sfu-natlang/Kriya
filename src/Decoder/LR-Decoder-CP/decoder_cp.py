# Synchronous CFG based Decoder for Machine Translation #

import operator
import os.path
import sys
import time

import settings
from parse_CP import Parse
from phraseTable import PhraseTable
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
from refPhrases import RefPhrases

def readNParse(sent_count):
    '''Parse the sentences in the array'''

    sent_indx = 0
    coverage_cnt = 0
    relaxed_decoding = False
    refsLst = []

    tot_time = 0.0
    inF = open(settings.opts.inFile, 'r')
    sys.stderr.write( "Reading sentences from file      : %s ...\n\n" % (settings.opts.inFile) )
    for sent in inF:
        sent = sent.strip()
        if settings.opts.force_decode: refsLst = getReferences(sent_indx)
        if settings.opts.skip_sents is not None and sent_indx < settings.opts.skip_sents:
            sent_indx += 1
            sent_count += 1
            continue

        parse_begin = time.time()
        parse_obj = Parse(sent_count, sent, relaxed_decoding, refsLst)
        sys.stderr.write( "%3d Translating  :: %s\n" % (sent_count, sent) )
        dec_status = parse_obj.parse()
        if ( dec_status == 99 ):
            parse_obj = ''
            relaxed_decoding = True
            parse_obj = Parse(sent_count, sent, relaxed_decoding, refsLst)
            dec_status = parse_obj.parse()
            relaxed_decoding = False
        parse_time = time.time() - parse_begin

        tot_time += parse_time
        sys.stderr.write( "Translation time :: %1.3g sec\n\n" % (parse_time) )
        sent_count += 1
        sent_indx += 1
        if settings.opts.force_decode: coverage_cnt += dec_status
        parse_obj = ''

    inF.close()
    sys.stderr.write( "Time taken for decoding the set      : %1.3g sec\n\n" % (tot_time) )
    if settings.opts.force_decode:
        sys.stderr.write( "Number of sentences covered      : %d\n" % (coverage_cnt) )
        sys.stderr.write( "%% of sentences covered           : %g\n" % (float(coverage_cnt) * 100/ float(sent_indx)) )

def getReferences(sent_indx):
    '''Get the references in an array for force decoding'''

    global refFiles
    refsLst = []
    refHLst = [ open(file, 'r') for file in refFiles ]
    for refH in refHLst:
        indx = 0
        for sent in refH:
            if indx == sent_indx:
                sent = sent.strip()
                refsLst.append(sent)
                break
            indx += 1
        refH.close()

    del refHLst[:]
    return refsLst

def getRefFiles():
    '''Get the reference files for forced decoding'''

    global refFiles
    refFiles = []
    if os.path.exists(settings.opts.refFile): refFiles.append(settings.opts.refFile)
    else:
        i = 0
        ref_i = settings.opts.refFile + str(i)
        while os.path.exists(ref_i):
            refFiles.append(ref_i)
            i += 1
            ref_i = settings.opts.refFile + str(i)

    if not refFiles:
        sys.stderr.write("ERROR: Forced decoding requires at least one reference file.\n")
        sys.stderr.write("       But, the specified reference file doesn't exist or isn't a valid prefix. Exiting!!\n\n")
        sys.exit(1)

def consolidateRules(cntsFile):

    sys.stderr.write( "Consolidating rules from file : %s ...\n" % (cntsFile) )
    rulesUsedDict = {}
    rC = open(cntsFile, 'r')
    try:
        for line in rC:
            (src, tgt, cnts) = line.split(" ||| ")
            rule = src + " ||| " + tgt
            if ( rulesUsedDict.has_key(rule) ): rulesUsedDict[rule] += int(cnts)
            else: rulesUsedDict[rule] = int(cnts)
    finally:
        rC.close()

    tot_used_rules = len(rulesUsedDict.keys())
    tot_PT_rules = PhraseTable.getTotalRules()
    sys.stderr.write( "Total SCFG rules found for the set           : %g\n" % (tot_PT_rules) )
    sys.stderr.write( "# of unique rules used in N-best derivations : %g\n" % (tot_used_rules) )
    sys.stderr.write( "%% of rules used in the N-best list           : %g\n" % ((float(tot_used_rules) * 100.0) / float(tot_PT_rules)) )
    wC = open(cntsFile, 'w')
    for rule, r_cnt in sorted(rulesUsedDict.iteritems(), key=operator.itemgetter(1)):
        wC.write( "%s ||| %d\n" % (rule, r_cnt) )
    wC.close()

def main():

    global refFiles
    sent_count = settings.opts.sentindex * settings.opts.sent_per_file

    sys.stderr.write( "Loading LM file %s ... \n" % (settings.opts.lmFile) )
    t_beg = time.time()
    if (not settings.opts.no_lm_score) and settings.opts.use_srilm: lm_obj = SRILangModel(settings.opts.n_gram_size, settings.opts.lmFile, settings.opts.elider)
    elif not settings.opts.no_lm_score: lm_obj = KENLangModel(settings.opts.n_gram_size, settings.opts.lmFile, settings.opts.elider)
    t_end = time.time()
    sys.stderr.write( "Time taken for loading LM        : %1.3f sec\n\n" % (t_end - t_beg) )

    if settings.opts.force_decode:
        getRefFiles()
        RefPhrases(sent_count, refFiles)
    #PhraseTable()
    TOT_TERMS = 0  ###TODO: change it to a parameter in settings
    in_Fp = open(settings.opts.inFile, 'r')
    for line in in_Fp:
        TOT_TERMS = max(len(line.strip().split()), TOT_TERMS)
    in_Fp.close()

    PhraseTable(TOT_TERMS)

    readNParse(sent_count)                      # Parse the sentences

    lm_obj = ''                                 # Calls the __del__ in {SRI/KEN}LangModel to free the LM variable

    #if settings.opts.trace_rules > 0:
    #    consolidateRules(settings.opts.outFile+".trace")

if __name__ == "__main__":

    settings.args()         # Set the different default parameters
    main()
