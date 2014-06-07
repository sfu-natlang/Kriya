#! /usr/bin/perl

my $nbest_file = $ARGV[0];
my $out_file = $ARGV[1];

my $prev_id = -1;
open(IN, $nbest_file);
open(OUT, ">$out_file");
while(<IN>) {
    chomp;
    my ($sent_id, $sent, $rest) = split(/\s*\|\|\|\s*/, $_);
    if ($sent_id != $prev_id) { print OUT "$sent\n"; }
    $prev_id = $sent_id;
}
close(IN);
close(OUT);
