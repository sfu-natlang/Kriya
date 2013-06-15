#! /usr/bin/python

# This program cleans the parallel corpus by ignoring lines when either the source or the target or both are empty

__author__="bsa33"
__date__ ="$Jan 11, 2010 3:32:35 PM$"

import sys

MAX_SENT_LEN = 80

def cleanCorpus(src_file, tgt_file, src_cleaned, tgt_cleaned):

    line_cnt = 0
    filt_line_cnt = 0
    sF = open(src_file, 'r')
    tF = open(tgt_file, 'r')
    oF1 = open(src_cleaned, 'w')
    oF2 = open(tgt_cleaned, 'w')

    while True:
        # read source and target lines
        src_line = sF.readline()
        tgt_line = tF.readline()
        if src_line == '' and tgt_line =='': break

        line_cnt += 1
        src_line = src_line.strip()
        tgt_line = tgt_line.strip()
        src_len = len( src_line.split() )
        tgt_len = len( tgt_line.split() )

        if src_len == 0 or src_len > MAX_SENT_LEN: continue
        elif tgt_len == 0 or tgt_len > MAX_SENT_LEN: continue
        else:
            oF1.write( "%s\n" % src_line )
            oF2.write( "%s\n" % tgt_line )
            filt_line_cnt += 1

    sF.close()
    tF.close()
    oF1.close()
    oF2.close()

    print "# of lines in corpus before cleaning : %d" % line_cnt
    print "# of lines in corpus after cleaning  : %d" % filt_line_cnt
    print "# of lines ignored in cleaning       : %d" % (line_cnt - filt_line_cnt)
    return None

def main():

    global MAX_SENT_LEN

    d_dir = sys.argv[1]
    out_dir = sys.argv[2]
    file_prefix = sys.argv[3]
    src = sys.argv[4]
    tgt = sys.argv[5]
    if len(sys.argv) == 7:
        try:
            MAX_SENT_LEN = int(sys.argv[6])
        except TypeError:
            print "\nERROR: Last argument should be the maximum sentence length (default 80)\n"
            sys.exit(1)

    if not d_dir.endswith("/"): d_dir += "/"
    if not out_dir.endswith("/"): out_dir += "/"
    src_file = d_dir + file_prefix + "." + src
    tgt_file = d_dir + file_prefix + "." + tgt
    src_cleaned = out_dir + file_prefix + ".cln." + src
    tgt_cleaned = out_dir + file_prefix + ".cln." + tgt

    cleanCorpus(src_file, tgt_file, src_cleaned, tgt_cleaned)

if __name__ == "__main__":
    main()
