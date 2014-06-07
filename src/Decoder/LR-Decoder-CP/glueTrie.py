# Implements a Suffix trie for faster searching of rules for a given span
# in the given synchronous grammar
# it is just a copy of myTrie.py which is used for storing glue rules

__author__="bsa33"
__date__ ="$Nov 12, 2009 3:20:39 PM$"


MAX_PHR_LEN = 5
pattern = ''
dfsStack = []
matchLst = []

class AbstractSuffixTree(object):
    '''Implements the base class for Suffix tree'''

    __slots__ = "__text", "_root", "_trie_size"

    # constructor
    def __init__(self, text):
        if len(text) and text.endswith("$$$"):
            self.__text = text
        else:
            self.__text = text + " $$$"
        self.__root = None
        self.trie_size = -1


class SimpleSuffixTreeForGlue(AbstractSuffixTree):
    '''Extends the AbstractSuffixTree'''

    __slots__ = "__text", "__root", "__trie_size", "__path_cnt"

    def __init__(self, text, total_terms=5):
        global MAX_PHR_LEN
        self.__text = text
        MAX_PHR_LEN = total_terms
        self.__path_cnt = 0
        self.__trie_size = 0
        self.__root = SuffixTreeNode()
        self.__constructTree()

    def addText(self, text):
        self.__text = text
        self.__constructTree()

    def __constructTree(self):

        wordsLst = []
        wordsLst = self.__text.split()
        wordsLst.append("$$$")

        nodes_added = SuffixTreeNode.addSuffix(self.__root, self.__root, wordsLst, self.__path_cnt)
        if nodes_added > 0:
            self.__trie_size += nodes_added
            self.__path_cnt += 1
        return None

    def printFullTree(self):
        SuffixTreeNode.printTree(self.__root, self.__root)
        return None

    def matchPattern(self, in_pattern):
        '''Returns all the suffix strings that match the given pattern'''

        global pattern
        global matchLst       # List of matching strings to be returned
        matchLst = []
        pattern = in_pattern
        wordsLst = []
        wordsLst = pattern.split()
        if len(wordsLst) == 0:
            print "Empty suffix- no valid suffix tree found for the input\n"
            sys.exit(1)

        wordsLst.append("$$$")
        SuffixTreeNode.dfSearch(self.__root, self.__root, wordsLst)
        return matchLst


class SuffixTreeNode(object):
    '''Implements the Node object for SuffixTree'''

    __slots__ = "__parent", "__label", "label_path", "__node_depth", "__branch_indx", "__childIndxDict"

    dfsStack = []

    def __init__(self, parent='NULL', str_label='', path='', node_depth=0, branch_indx=-1):
        self.__parent = parent
        self.__label = str_label
        self.label_path = path
        self.__node_depth = node_depth
        self.__branch_indx = branch_indx
        self.__childIndxDict = {}

    def addSuffix(self, root_node, wordsLst, path_cnt):
        '''Add the given suffix in the tree: uses __search() and __insert()'''

        wLst = []
        for w in wordsLst: wLst.append(w)
        (ptr, ins_at_node) = self.__search(root_node, wLst)
        return self.__insert(ins_at_node, ptr, wLst, path_cnt)

    def __search(self, curr_node, wLst):
        '''Search the tree and identify the position for inserting the suffix'''

        if len(wLst) == 1:
            print 'Empty suffix- no valid suffix tree found for the input'
            sys.exit(1)

        # @type curr_node SimpleSuffixTreeForGlue
        ptr = 0
        while True:
            new_label = wLst[ptr]
            if curr_node.__childIndxDict.has_key(new_label):
                child_node = curr_node.__childIndxDict[new_label]
                ptr += 1
                curr_node = child_node
                if len(wLst) == 0:
                    break
            else:
                break

        return (ptr, curr_node)

    def __insert(self, ins_at_node, ptr, wLst, path_cnt):
        '''Inserts a node at the specified position in the tree, returns # of new paths created'''

        path = ''
        tot_nodes_added = 0
        patt_len = len(wLst)
        for pos in range( ptr, patt_len ):
            str_label = wLst[pos]
            if pos == patt_len - 1: path = ' '.join( wLst[0:pos] )
            else: path = ' '.join( wLst[0:pos+1] )
            child_node = SuffixTreeNode(ins_at_node, str_label, path, ins_at_node.__node_depth + 1, path_cnt)
            ins_at_node.__childIndxDict[str_label] = child_node
            tot_nodes_added += 1
            ins_at_node = child_node

        return tot_nodes_added

    def printTree(self, root_node):
        '''Use DFS algorithm to print the tree'''

        tot_nodes = 0
        nodesVisited = []
        nodesVisited.append( root_node )
        while nodesVisited:
            curr_node = nodesVisited.pop()
            for child_label in curr_node.__childIndxDict.keys():
                if child_label == "$$$":
                    # @type child_label SuffixTreeNode
                    print "Path : ", child_label.label_path
                    tot_nodes += 1
                    continue
                child_node = curr_node.__childIndxDict[child_label]
                nodesVisited.append( child_node )

        print "Total nodes in Trie :", tot_nodes
        return None

    def dfSearch(self, root_node, wLst):
        '''Implements the Depth-First Search (w/ special routines) for matching patterns'''

        global MAX_PHR_LEN
        global dfsStack
        dfsStack = []
        dfsStack.append( (root_node, 0, []) )
        patt_len = len(wLst)

        while len(dfsStack) > 0:
            sIndxLst = []

            (curr_node, search_indx, sIndxLst) = dfsStack.pop()   # get the lastly added element from the stack
            # @type curr_node SuffixTreeNode
            search_label = wLst[search_indx]
            curr_label = curr_node.getStrLabel()
            curr_node_depth = curr_node.getNodeDepth()
            if curr_label[0:3] == "X__": prev_match = search_indx - curr_node_depth + 1    #Maryam
            else: prev_match = 0

            # a non-terminal X__1 or X__2 is found in the current node
            if search_label != "$$$" and (curr_node.__childIndxDict.has_key("X__1") or curr_node.__childIndxDict.has_key("X__2") or curr_node.__childIndxDict.has_key("X__3")):   #TO-DO: it may have more than two non-terminal

                # a nonterminal is the child of the current node
                for child in ["X__1","X__2", "X__3"]:
		    if not curr_node.__childIndxDict.has_key(child): continue	#TO-DO: it may have more than two non-terminal  Maryam
                      
                    spanIndxLst = sIndxLst[:]
		    if curr_label[0:3] == 'X__':
	                spanIndxLst.append( search_indx - 1)
			
	            spanIndxLst.append( search_indx )
                    new_node = curr_node.__childIndxDict[child]
                    new_search_indx = search_indx + 1
                    self.__processNewNode( new_node, new_search_indx, patt_len, spanIndxLst )

            # the word at the current position is found in the Trie
            if curr_node.__childIndxDict.has_key(search_label):
                new_node = curr_node.__childIndxDict[search_label]
                new_search_indx = search_indx + 1
                spanIndxLst = []
                for i in sIndxLst: spanIndxLst.append(i)
                if prev_match > 0:
                    spanIndxLst.append( search_indx - 1 )
                self.__processNewNode( new_node, new_search_indx, patt_len, spanIndxLst )

            # non-terminal X__? continues for the current position in the given pattern; or
            # also used when the word at the current position is not found in the Trie
            if prev_match > 0 and prev_match < MAX_PHR_LEN:
                new_search_indx = search_indx + 1
                spanIndxLst = []
                for i in sIndxLst: spanIndxLst.append(i)
                if new_search_indx < patt_len:
                    self.__processNewNode( curr_node, new_search_indx, patt_len, spanIndxLst )

        return None

    def __processNewNode(self, new_node, new_search_indx, patt_len, spanIndxLst=[]):

        global dfsStack
        global matchLst

        if new_search_indx < patt_len:
            dfsStack.append( (new_node, new_search_indx, spanIndxLst) )
        else:
            if new_node.isLeaf():
                # @type new_node SuffixTreeNode
                matchLst.append( (new_node.label_path, spanIndxLst) )

        return None

    def isRoot(self):
        if self.parent == 'NULL':
            return True
        return False

    def isLeaf(self):
        if self.__childIndxDict:
            return False
        return True

    def isEndofSuffix(self):
        if self.__childIndxDict.has_key("$$$"):
            return True
        return False

    def getNodeDepth(self):
        return self.__node_depth

    def getStrLabel(self):
        return self.__label
