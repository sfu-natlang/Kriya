#!/usr/bin/perl -w

use Cwd 'abs_path';
use File::Basename;

use strict;

my $stem = $ARGV[0];
my $NBest_file = $ARGV[1];
my $met_dir = $ARGV[2];

if (!defined $stem) {
  print STDERR "usage: multi-sent-bleu.pl references hypothesis met_dir\n";
  print STDERR "References could be comma separated or a single stem (will be expanded as reference0, reference1, ...)\n";
  exit(1);
}

if(!defined $ENV{PY3_HOME}) { die "**ERROR: Needs the Environmental variable PY3_HOME to be defined. Exiting!!\n"; }
my $ribes_scrpt = abs_path(dirname($0))."/RIBES.py";
$met_dir =~ s/\/$//;

my $ref = 0;
my @REF;
if ($stem =~ /,/) {
    foreach my $ref_file (split(/,/, $stem)) {
        &add_to_ref($ref_file,\@REF);
        $ref++;
    }
}
else {
    $stem .= ".ref" if !-e $stem && !-e $stem."0" && -e $stem.".ref0";

    while(-e "$stem$ref") {
        &add_to_ref("$stem$ref",\@REF);
        $ref++;
    }
    if (-e $stem) {
        &add_to_ref($stem,\@REF);
        $ref++;
    }
}

# Create ref and hyp files in RIBES format (one sentence per line)
my @refH = ();
my @refFiles = ();
for (my $i=0; $i<$ref; $i++) {
    my $ref_out_file = "${met_dir}/ribes.ref.out${i}";
    open (my $rH, ">:utf8", $ref_out_file) or die "Can't open $ref_out_file for writing: $!";
    push @refH, $rH;
    push @refFiles, $ref_out_file;
}
my $hyp_out_file = "${met_dir}/ribes.hyp.out";
open (my $hH, ">:utf8", $hyp_out_file) or die "Can't open $hyp_out_file for writing: $!";

my $i;
open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
while (<HYP>){
    chop;
    my @PARTS=split(/\s*\|\|\|\s*/,$_);
    my $Hyp = $PARTS[1];
    my $refNum = $PARTS[0];
    $Hyp =~ s/^\s+|\s+$//g;
    $Hyp =~ s/\s+/ /g;

    print $hH "$Hyp\n";
    my $thisReferenes = $REF[$refNum];
    $i = 0;
    foreach my $reference (@{$thisReferenes}) {
        #print $i, " ** ", $refH[$i];
        print { $refH[$i] } "$reference\n";
        $i++;
    }
}
close(HYP);
close($hH);
foreach my $rH (@refH) { close($rH); }

# Now call the Ribes python script to get sentence-level Ribes score on the hyp file for the given references
my $ref_files_opt = "";
foreach my $ref_out_file (@refFiles) {
    $ref_files_opt .= " -r $ref_out_file";
}
$ref_files_opt =~ s/^\s+//;
my $cmd = "$ENV{PY3_HOME}/bin/python3 $ribes_scrpt -s $ref_files_opt -o $met_dir/ribes.out.ribes $hyp_out_file";
safesystem($cmd);


sub add_to_ref {
    my ($file, $REF) = @_;
    my $s=0;
    open(REF,$file) or die "Can't read $file";
    while(<REF>) {
        chop;
        s/^\s+|\s+$//g;
        s/\s+/ /g;
        push @{$$REF[$s++]}, $_;
    }
    close(REF);
}

sub safesystem {
    print STDERR "Executing: @_\n";
    system(@_);
    if ($? == -1) {
        print STDERR "Failed to execute: @_\n  $!\n";
        exit(1);
    }
    elsif ($? & 127) {
        printf STDERR "Execution of: @_\n  died with signal %d, %s coredump\n",
        ($? & 127),  ($? & 128) ? 'with' : 'without';
        exit 1;
    }
    else {
        my $exitcode = $? >> 8;
        print STDERR "Exit code: $exitcode\n" if $exitcode;
        return ! $exitcode;
    }
}

