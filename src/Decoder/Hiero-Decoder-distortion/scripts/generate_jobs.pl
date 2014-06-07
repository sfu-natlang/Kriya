## Generate the job script for submission with qsub ##

use strict;

my $fh;
my $i;

for ($i=1501; $i<2000; $i+=10) {
    my $oFile = "job_".$i.".sh";

    my @cmd = ();
    #push(@cmd, "#PBS -l mem=1gb -l walltime=00:30:00 -m a -M bsa33\@sfu.ca");
    push(@cmd, "/usr/bin/env python \$dd/sufTreeFilter.py $i /cs/natlang-expts/bsa33/rules/filtered/devset_rules1.out /cs/natlang-scratch/scratch/bsa33/devset-sent /cs/natlang-scratch/scratch/bsa33/devset-rules-new");

    open($fh, ">$oFile") or die "Could not open $oFile for writing\n";
    print $fh join("\n", @cmd),"\n";
    close($fh);
}
