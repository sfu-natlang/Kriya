## This program filters rules for the sentences in the devset ##
## This is expected to use minimal memory and faster execution time ##

use strict;
use warnings;

# Constants
my $TOT_SENT;
my $MAX_PHR_LEN = 10;

# Data and rule files - Path and file names
my $rule_indx = $ARGV[0];
my $data_file = $ARgv[1];
my $rule_file = $ARGV[2];
my $out_dir = $ARGV[3];

# Global variables
my @sentences = ();
my %phrSentHsh = ();
my %sentPhrPosHoH = ();
my %datasetWrds = ();

my $rules_to_process = 5000000;
my $out_file = $out_dir . "$rule_indx.out";

loadDataSet($data_file);
readRules($rule_file, $rule_indx, $out_file);

sub loadDataSet {
    my $inFile = shift;
    print "Reading dataset from file : $inFile ...\n";

    my $i;
    my $j;
    my $word;
    my $phr;
    my $sent_id = 0;
    my @words = ();

    open(INF, $inFile) || die "\nI/O Error: Error in reading from dataset file $inFile. Exiting!\n\n";
    while(<INF>) {
	chomp;

	push(@sentences, $_);
	@words = ();
	@words = split(/\s+/, $_);
	for( $i = 0; $i < scalar(@words); $i++ ) {
	    for( $j = $i; $j < ($i + 10) && $j < scalar(@words); $j++ ) {
		$phr = join(' ', @words[$i .. $j]);

		# Hash the sentence index for the phrase
		if( !exists $phrSentHsh{$phr} ) {
		    @{ $phrSentHsh{$phr} } = ($sent_id);
		}
		elsif ( $phrSentHsh{$phr}[scalar( @{$phrSentHsh{$phr}} )-1] != $sent_id ) {
		    push( @{ $phrSentHsh{$phr} }, $sent_id );
		}

		# Hash the phrase and position info for the sentence index
		if( !exists $sentPhrPosHoH{$sent_id}{$phr} ) {
		    $sentPhrPosHoH{$sent_id}{$phr} = $i;
		}
		else { $sentPhrPosHoH{$sent_id}{$phr} .= ':' . $i; }
	    }
	}
	$sent_id++;
    }
    close(INF);
    $TOT_SENT = $sent_id;
    print "Total sentences : $TOT_SENT\n";
}


sub readRules {
    my $ruleFile = shift;
    my $rule_indx = shift;
    my $outFile = shift;

    my $from_rule = ( ($rule_indx - 1) * $rules_to_process ) + 1;
    my $to_rule = $from_rule + $rules_to_process;

    print "From rule : $from_rule\nTo rule   : $to_rule\n\n";
    print "Reading rules from file   : $ruleFile ...\n";
    my $rule_id = 0;
    my $prev_rule = "";
    my $rule_positive = 1;
    my $src_rule;
    my $phr;
    my $rule_entry;
    my $filtered_rule_cnt = 0;
    my @phrases = ();
    my @other_entries = ();

    open(RF, $ruleFile) || die "\nI/O Error: Error in reading from rule file $ruleFile. Exiting!\n\n";;
    open(OUTF, ">$outFile") || die "\nI/O Error: Error in writing to output file $outFile. Exiting!\n\n";;
    while(<RF>) {
	chomp;

	$rule_id++;
	if ($rule_id < $from_rule) { next; }
	if ($rule_id >= $to_rule) { last; }

	$rule_entry = $_;
	($src_rule, @other_entries) = split(/\s\|\|\|\s/, $rule_entry);

	if($rule_id == 1) { $prev_rule = $src_rule; }
	elsif($prev_rule eq $src_rule) {
	    if($rule_positive) {
		$filtered_rule_cnt++;
		print OUTF "$rule_entry\n";
	    }
	    next;
	}

	@phrases = ();
	$prev_rule = $src_rule;
	$rule_positive = 1;

	# Checks if 'all' the phrases (consecutive terminal words) in a rule are found in the dataset
	foreach $phr ( split(/\s?(X__\d)\s?/, $src_rule) ) {
	    next if ( length($phr) == 0 );         # Skip the leading or trailing 'empty' phrases

	    push(@phrases, $phr);
	    if ( $phr ne 'X__1' && $phr ne 'X__2' && !exists $phrSentHsh{$phr} ) {
		$rule_positive = 0;
		last;
	    }
	}

	if ( $rule_positive ) {
	    if( scalar(@phrases) == 1 ) {      # If rule has no non-terminals, add it as a positive rule
		$filtered_rule_cnt++;
		print OUTF "$rule_entry\n";
	    }
	    else {                             # else, verify if the rule is relevant for the dataset
		$rule_positive = checkRule($src_rule, \@phrases);
		if( $rule_positive ) {
		    $filtered_rule_cnt++;
		    print OUTF "$rule_entry\n";
		}
	    }
	}

	# track progress (every ten million rules)
	if ( $rule_id % 10000000 == 0 ) { print "Processed $rule_id rules ...\n"; }
    }
    close(RF);
    close(OUTF);
    print "Total # of filtered rules : $filtered_rule_cnt\n";
}


sub checkRule {
    my $rule = shift;
    my $phr_ref = shift;

    my $i;
    my $phr;
    my $sent;
    my $sent_id;
    my $offset;
    my $beg_pos;
    my $new_pos;
    my $prev_pos;
    my $phr_len;
    my $sent_len;
    my $found_X = 0;
    my $rule_positive = 0;
    my $ignore_sent = 0;

    my @phrases = @$phr_ref;
    my @sent_wrds = ();
    my @pos_arr = ();
    my @intersection = ();
    my @phrlen_arr = ();
    my @wrd_arr = ();


    for($i = 0; $i < scalar(@phrases); $i++) {
	@wrd_arr = ();
	@wrd_arr = split(/\s/, $phrases[$i]);
	$phrlen_arr[$i] = scalar( @wrd_arr );
    }

    @intersection = @{ getIntersectingRules($phr_ref) };
    foreach $sent_id (@intersection) {

	$found_X = 0;
	@pos_arr = ();
	$sent = $sentences[$sent_id];
	@sent_wrds = split(/\s/, $sent);
	$sent_len = scalar(@sent_wrds);

	for($i = 0; $i < scalar(@phrases); $i++) {
	    $phr = $phrases[$i];

	    if( $phr eq 'X__1') {
		if( $i == 0 ) { $beg_pos = 'X'; $pos_arr[$i] = 'X'; }
		else {
		    $offset = $phrlen_arr[$i-1];
		    ($ignore_sent, $pos_arr[$i]) = getCurrXPos($prev_pos, $offset, $sent_len);
		}
		$found_X = 1;
	    }
	    elsif( $phr eq 'X__2') {
		$offset = $phrlen_arr[$i-1];
		($ignore_sent, $pos_arr[$i]) = getCurrXPos($prev_pos, $offset, $sent_len);
		$found_X = 1;
	    }
	    else {
		$new_pos = $sentPhrPosHoH{$sent_id}{$phr};
		if( $found_X ) {
		    if( $i == 1 ) {
			$offset = 1;
			($ignore_sent, $beg_pos) = getPrevPos($new_pos, $offset);
			$pos_arr[$i-1] = $beg_pos;
			$prev_pos = $pos_arr[$i-1];
		    }
		    $phr_len = $phrlen_arr[$i];
		    ($ignore_sent, $pos_arr[$i]) = getCurrPos($prev_pos, $new_pos, $phr_len, $beg_pos);
		    $found_X = 0;
		}
		else {
		    $pos_arr[$i] = $new_pos;
		    if( $i == 0 ) { $beg_pos = $new_pos; }
		}
	    }
	    $prev_pos = $pos_arr[$i];
	    if( $ignore_sent ) { last; }
	}
	if ( $ignore_sent ) { $ignore_sent = 0; }
	else { $rule_positive = 1; last; }
    }
    return $rule_positive;
}


sub getCurrXPos {
    my $prev_pos = shift;
    my $offset = shift;
    my $sent_len = shift;

    my $pos_str;
    my $possible_pos;
    my $rule_mismatch = 1;
    my @tmp_arr = ();

    foreach my $pos ( split(/:/, $prev_pos) ) {
	$possible_pos = $pos + $offset;
	if( $possible_pos < $sent_len ) {
	    push(@tmp_arr, $possible_pos);
	    $rule_mismatch = 0;
	}
    }
    $pos_str = join(':', @tmp_arr);
    return ($rule_mismatch, $pos_str);
}


sub getPrevPos {
    my $new_pos = shift;
    my $offset = shift;

    my $pos_str;
    my $possible_pos;
    my $rule_mismatch = 1;
    my @tmp_arr = ();

    foreach my $pos ( split(/:/, $new_pos) ) {
	$possible_pos = $pos - $offset;
	if( $possible_pos > 0 ) {
	    push(@tmp_arr, $possible_pos);
	    $rule_mismatch = 0;
	}
    }
    $pos_str = join(':', @tmp_arr);
    return ($rule_mismatch, $pos_str);
}


sub getCurrPos {
    my $prev_pos = shift;
    my $new_pos = shift;
    my $phr_len = shift;
    my $beg_pos = shift;

    my $bpos, my $npos, my $ppos;
    my $offset;
    my $pos_str;
    my $rule_mismatch = 1;
    my @tmp_arr = ();

    foreach $ppos ( split(/:/, $prev_pos) ) {
	foreach $npos ( split(/:/, $new_pos) ) {
	    $offset = $npos - $ppos;
	    if( $offset >= 1) {
		foreach $bpos ( split(/:/, $beg_pos) ) {
		    if( ($npos + $phr_len - $bpos) < $MAX_PHR_LEN ) {
			push(@tmp_arr, $npos);
			$rule_mismatch = 0;
		    }
		}
	    }
	}
    }
    $pos_str = join(':', @tmp_arr);
    return ($rule_mismatch, $pos_str);
}


sub getIntersectingRules() {
    my $phr_ref = shift;

    my $phr;
    my $sent_id;
    my $tot_phrases = 0;
    my $largest_id = $TOT_SENT;
    my @intersection = ();
    my %sent_cnt_hsh = ();
    my %countHsh = ();

    foreach $phr ( @$phr_ref ) {
	next if ($phr eq 'X__1' || $phr eq 'X__2');
	$sent_cnt_hsh{$phr} = scalar( @{ $phrSentHsh{$phr} } );
	if( $largest_id > $phrSentHsh{$phr}[scalar( @{$phrSentHsh{$phr}} )-1] ) {
	    $largest_id = $phrSentHsh{$phr}[scalar( @{$phrSentHsh{$phr}} )-1];
	}
    }

    for $phr (sort { $sent_cnt_hsh{$a} <=> $sent_cnt_hsh{$b} } keys %sent_cnt_hsh) {
	foreach $sent_id ( @{ $phrSentHsh{$phr} } ) {
	    last if( $sent_id > $largest_id );    # Skip the remaining sentence ids as they are > than largest id
	    $countHsh{$sent_id}++;
	}
	$tot_phrases++;
    }

    foreach $sent_id (sort {$a <=> $b} keys %countHsh) {
	$countHsh{$sent_id} == $tot_phrases ? push @intersection, $sent_id : 1;
    }

    return \@intersection;
}
