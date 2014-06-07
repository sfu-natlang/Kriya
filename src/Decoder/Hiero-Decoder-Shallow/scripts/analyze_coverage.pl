#! /usr/bin/perl

## Command for ar-en:
# cd  /cs/vml2/NATLANG/users/bsa33/ar-en
# perl ~/svnroot/bsa33/src/Hiero-Decoder-Shallow/scripts/analyze_coverage.pl training/pre-processed/10K-random/train.tok.ar training/pre-processed/10K-random/train.tok.en coverage/sh-kriya/ training/phr-alignments/moses/all.ar-en.outspan
## Command for fr-en:
# cd /cs/vml2/NATLANG/users/bsa33/wmt10/fr-en
# perl /cs/grad2/bsa33/svnroot/bsa33/src/Hiero-Decoder-Shallow/scripts/analyze_coverage.pl coverage/10K-random/no-undoc.fr-en.lc.0-0.fr coverage/10K-random/no-undoc.fr-en.lc.0-0.en coverage/sh-kriya/ phr-alignments/moses/all.fr-en.outspan
##

use strict;

my $line;
my %revSrcHsh = ();
my %srcSentsHsh = ();
my %refSentsHsh = ();
my %srcToksHsh = ();
my %tgtToksHsh = ();
my %srcUnaligned = ();
my %tgtUnaligned = ();

my $src_file = $ARGV[0];
my $ref_file = $ARGV[1];
my $nbest_dir = $ARGV[2];
my $outspan_file = $ARGV[3];
my $analyze_reachable = (defined $ARGV[4]) ? $ARGV[4] : 0;

die "Last argument should be 1 or 0 indicating whether to analyze reachable or not. Exiting!!\n" if ($analyze_reachable !~ /^[01]$/);
my $what_is_analyzed = ($analyze_reachable) ? "Reachable" : "Unreachable";

loadSrcRefSents($src_file, 1);
loadSrcRefSents($ref_file, 0);
identifyUnreachables();
countUnreachableToks();
checkAlignments();
printStats();

print STDERR "$what_is_analyzed source sentences remaining ...\n";
foreach (values %srcSentsHsh) { print STDERR "$_\n"; }
print STDERR "\n$what_is_analyzed target sentences remaining ...\n";
foreach (values %refSentsHsh) { print STDERR "$_\n"; }


sub loadSrcRefSents {
    my $file = shift;
    my $is_src = shift;

    my $sent_indx = 0;
    open(IN, $file);
    while(<IN>) {
        chomp;
        if ($is_src) { $srcSentsHsh{$sent_indx} = $_; }
        else { $refSentsHsh{$sent_indx} = $_; }
        $sent_indx++;
    }
    if ($is_src) { printf STDERR "Number of source sentences      : %d\n", $.; }
    else { printf STDERR "Number of reference sentences   : %d\n", $.; }
    close(IN);
}

sub identifyUnreachables {
    my @nbestFiles = &getNbestFiles();
    my $id;
    my $sent;
    my $nbest_out;
    my %coveredHsh = ();

    foreach my $nbest_file (@nbestFiles) {
        open(NB, $nbest_file);
        while(<NB>) {
            chomp;
            ($id, $nbest_out) = split(/\|\|\|/);
            if (!$analyze_reachable) {
                if (exists $refSentsHsh{$id}) {
                    delete $srcSentsHsh{$id};
                    delete $refSentsHsh{$id};
                }
                else { die("Nbest sentence index $id doesn't exist in references\n"); }
            }
            elsif ($analyze_reachable) { $coveredHsh{$id} = 1; }
        }
        close(NB);
    }

    if ($analyze_reachable) {
        foreach $id (keys %srcSentsHsh) {
            if (!exists $coveredHsh{$id}) {
                delete $srcSentsHsh{$id};
                delete $refSentsHsh{$id};
            }
        }
    }

    foreach $id (keys %srcSentsHsh) {
        $sent = $srcSentsHsh{$id};
        if (!exists $revSrcHsh{$sent}) { @{$revSrcHsh{$sent}} = (); }
        push @{$revSrcHsh{$sent}}, $id;
    }
    printf STDERR "Number of $what_is_analyzed sentences : %d\n", scalar (keys %srcSentsHsh);
}

sub countUnreachableToks {
    my $tok;
    foreach (values %srcSentsHsh) {
        foreach $tok (split/\s+/) { $srcToksHsh{$tok}++; }
    }

    foreach (values %refSentsHsh) {
        foreach $tok (split/\s+/) { $tgtToksHsh{$tok}++; }
    }
}

sub getNbestFiles {
    $nbest_dir =~ s/\/$//;
    return <$nbest_dir/nbest.*>;
}

sub checkAlignments {

    my $ignore_sent = 0;
    my $unreachable_cnt = 0;
    my $tok;
    my $sent_id;
    my $src_sent;
    my $tgt_sent;
    my $s_pos;
    my $t_pos;
    my $align;
    my %srcPosHsh = ();
    my %tgtPosHsh = ();

    my $found_unaligned_src;
    my $found_unaligned_tgt;
    my $unaligned_src = 0;
    my $unaligned_tgt = 0;
    my $unaligned_both = 0;
    my $unaligned_neither = 0;

    print STDERR "Now reading the outspan files to identify unaligned source and target words ...\n";
    open(AL, $outspan_file);
    while(<AL>) {
        chomp;
        if ($_ =~ /^LOG: PHRASES_END:/) {
            $sent_id = -1;
            $ignore_sent = 0;
            $src_sent = "";
            $tgt_sent = "";
            $align = "";
            %srcPosHsh = ();
            %tgtPosHsh = ();
            next;
        }
        elsif ($ignore_sent || $_ =~ /^\d/ || $_ =~ /^LOG: PHRASES_BEGIN:/) { next; }

        if ($_ =~ /^LOG: SRC:/) {
            s/^LOG: SRC: //;
            s/^\s+|\s+$//g;
            if (!exists $revSrcHsh{$_}) {
                $ignore_sent = 1;
                next;
            }

            $src_sent = $_;
            $s_pos = 0;
            foreach $tok (split/\s+/) { $srcPosHsh{$s_pos++} = $tok; }
        }
        elsif ($_ =~ /^LOG: TGT:/) {
            s/^LOG: TGT: //;
            s/^\s+|\s+$//g;
            $tgt_sent = $_;
            $t_pos = 0;
            foreach $tok (split/\s+/) { $tgtPosHsh{$t_pos++} = $tok; }

            # Get the correct sentence id by matching both source and reference sentences
            for (my $i=0; $i<scalar( @{$revSrcHsh{$src_sent}} ); $i++) {
                $sent_id = $revSrcHsh{$src_sent}[$i];
                if ($refSentsHsh{$sent_id} eq $tgt_sent) { last; }
                $sent_id = -1
            }
        }
        elsif ($_ =~ /^LOG: ALT:/) {
            next if ($sent_id == -1);
            $unreachable_cnt++;
            s/^LOG: ALT: //;

            foreach $align ( split(/\s+/) ) {
                ($s_pos, $t_pos) = split(/\-/, $align);
                if (exists $srcPosHsh{$s_pos}) { delete $srcPosHsh{$s_pos}; }
                if (exists $tgtPosHsh{$t_pos}) { delete $tgtPosHsh{$t_pos}; }
            }

            $found_unaligned_src = 0;
            foreach $tok (values %srcPosHsh) {
                $found_unaligned_src = 1 if (!$found_unaligned_src);
                $srcUnaligned{$tok}++;
            }

            $found_unaligned_tgt = 0;
            foreach $tok (values %tgtPosHsh) {
                $found_unaligned_tgt = 1 if (!$found_unaligned_tgt);
                $tgtUnaligned{$tok}++;
            }

            if ($found_unaligned_src && $found_unaligned_tgt) { $unaligned_both++; }
            elsif ($found_unaligned_src && !$found_unaligned_tgt) { $unaligned_src++; }
            elsif (!$found_unaligned_src && $found_unaligned_tgt) { $unaligned_tgt++; }
            elsif (!$found_unaligned_src && !$found_unaligned_tgt) {
                $unaligned_neither++;
                print "  ** Found neither unaligned\n\t$src_sent\n\t$tgt_sent\n\t$_\n\n";
            }

            for (my $i=0; $i<scalar( @{$revSrcHsh{$src_sent}} ); $i++) {
                if ($sent_id == $revSrcHsh{$src_sent}[$i]) {
                    delete $revSrcHsh{$src_sent}[$i];
                    last;
                }
            }
            if (scalar ( @{$revSrcHsh{$src_sent}} ) == 0) { delete $revSrcHsh{$src_sent}; }

            delete $srcSentsHsh{$sent_id};
            delete $refSentsHsh{$sent_id};
        }
    }
    close(AL);
    printf STDERR "Total $what_is_analyzed sentences processed         : %d\n", $unreachable_cnt;
    printf STDERR "Sentences with both src & tgt words unaligned : %d\n", $unaligned_both;
    printf STDERR "Sentences with unaligned source words         : %d\n", $unaligned_src;
    printf STDERR "Sentences with unaligned target words         : %d\n", $unaligned_tgt;
    printf STDERR "Sentences with no unaligned src & tgt words   : %d\n\n", $unaligned_neither;
}

sub printStats {
    my $unaligned;
    print "=== Unaligned source words ===\n";
    foreach $unaligned (sort {$srcUnaligned{$b} <=> $srcUnaligned{$a}} keys %srcUnaligned) {
        if (!exists $srcToksHsh{$unaligned}) { printf STDERR "Token %s not found in srcToksHsh\n", $unaligned; }
        printf "%s\t%d\n", $unaligned, $srcUnaligned{$unaligned};
    }

    print "\n=== Unaligned target words ===\n";
    foreach $unaligned (sort {$tgtUnaligned{$b} <=> $tgtUnaligned{$a}} keys %tgtUnaligned) {
        if (!exists $tgtToksHsh{$unaligned}) { printf STDERR "Token %s not found in tgtToksHsh\n", $unaligned; }
        printf "%s\t%d\n", $unaligned, $tgtUnaligned{$unaligned};
    }
}

