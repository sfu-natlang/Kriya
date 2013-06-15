## This program splits the data-file into different parts having some specific # of sentences ##
## The no of sentences in each file is specified by the first argument ##

import sys, os

def splitSpanFile(SENT_PER_FILE, inFile, outDir):
    sent_count = 0

    j = 1
    out_suffix = '.outspan'

    if outDir.endswith('/'): outFile = outDir + str(j) + out_suffix
    else: outFile = outDir + '/' + str(j) + out_suffix
    outF = open(outFile, 'w')
    print 'Writing in file: ', outFile

    inF = open(inFile, 'r')
    for line in inF:
        if line.startswith('LOG: PHRASES_END:'):
            sent_count += 1
        outF.write(line)

        if sent_count % SENT_PER_FILE == 0 and sent_count > 0:
            sent_count = 0
            outF.close()
            j += 1

            if outDir.endswith('/'): outFile = outDir + str(j) + out_suffix
            else: outFile = outDir + '/' + str(j) + out_suffix
            outF = open(outFile, 'w')
            print 'Writing in file: ', outFile

    inF.close()
    outF.close()


def main():

    sent_per_file = int(sys.argv[1])
    spanFile = sys.argv[2]
    outDir = sys.argv[3]
    splitSpanFile(sent_per_file, spanFile, outDir)


if __name__ == '__main__':
    main()

