## This program splits the data-file into different parts having some specific # of sentences ##
## The no of sentences in each file is specified by a global constant ##

import codecs, os, sys

# Constants
out_prfx = ""
SENT_PER_FILE = 100

def splitSpanFile(inFile, outDir):

    global out_prfx
    global SENT_PER_FILE
    j = 1
    sent_count = 0
    out_suffix = '.out'

    outFile = outDir + out_prfx + str(j) + out_suffix
    print 'Writing in file: ', outFile

    oF = codecs.open(outFile, 'w', 'utf-8')
    with codecs.open(inFile, 'r', 'utf-8') as iF:
        for line in iF:
            sent_count += 1
            oF.write(line)

            if sent_count % SENT_PER_FILE == 0 and sent_count > 0:
                oF.close()
                j += 1
                sent_count = 0
                outFile = outDir + out_prfx + str(j) + out_suffix
                oF = codecs.open(outFile, 'w','utf-8')
                print 'Writing in file: ', outFile

    oF.close()
    print "Total items in the consolidated file : %d" % (sent_count)

def main():
    global out_prfx
    global SENT_PER_FILE

    inFile = sys.argv[1]
    outDir = sys.argv[2]
    if( len(sys.argv) >= 4 ):
        SENT_PER_FILE = int( sys.argv[3] )
        if( len(sys.argv) > 4 ):
            out_prfx = sys.argv[4]

    if not outDir.endswith('/'): outDir = outDir + '/'
    splitSpanFile(inFile, outDir)

if __name__ == '__main__':
    main()

