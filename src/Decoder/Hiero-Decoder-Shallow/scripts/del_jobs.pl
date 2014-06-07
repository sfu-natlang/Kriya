use strict;

my $beg_id = $ARGV[0];
my $end_id = $ARGV[1];

for(my $i = $beg_id; $i <= $end_id; $i++) {
	system("qdel", "$i");
}

