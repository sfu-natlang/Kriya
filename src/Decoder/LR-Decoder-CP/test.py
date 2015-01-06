import time

d={}
#for i in range(200000):
#	d[i] = 0

a = range(100)
b = range(-100,0)
ruleLst = []
parse_begin = time.time()
#n=0
for i in range(-100,900):
     ruleLst[len(ruleLst):] = [ a[:] ]
     ruleLst[len(ruleLst):] = [ b[:] ]
    # k = d.get(i, -1)
     #l=[]
     #for k in range(20):
     #        l.append(0)
     #n+=len(l)
     #for k in d.keys():
     #	n = 0
parse_time = time.time() - parse_begin
print "%1.5g sec\n" % (parse_time)

ruleLst = []
parse_begin = time.time()
#n=0
for i in range(-100,900):
     ruleLst.append([ a[:] ])
     ruleLst.append([ b[:] ])
     #k = d[i] if i in d else -1
     #if i not in d: n=0
     #l=[]
     #for k in range(20):
     #        n+=1
     #        l.append(0)
     #for k in d:
     #	n = 0
parse_time = time.time() - parse_begin
print "%1.5g sec\n" % (parse_time)

def fun():
	a = range(100)
	b = range(300)
	#return a if True else [], b if False else []
	return 0 in b
print fun()

#r,l = fun()
#print len(r)
#print len(l)

class t:
	def __init__(self, input):
		self.span = input
		self.cover = frozenset(range(input[0], input[1]))
		self.hashval = hash((self.cover, input))

	def __hash__(self):
		print self.hashval, hash(self.hashval)
		return self.hashval
	def __eq__(self, other):
		return self.hashval==other.hashval
	def __str__(self):
		return str(self.span)+" "+str(self.cover)

a = t((1,2))
b = t((3,4))
c = t((4,5))
n = t((1,2))

d={}
d[a] = [1]
d[b] = n
d[c] = [3]
print "before"
if n in d:
	print "yes" 
	d[n].append(1)

print "after"
for key in d:
	print str(key)

print d[a]
d = {}
print str(n)


#r = Distortion("a b cc X__1 d ff X__2", "a cc b ff dd k X__2 X__1")
#print r.getValue([5,4])  ## 22

#r = Distortion("a b cc X__1 d ff X__2 dd dd", "a cc b ff dd k X__2 X__1")
#print r.getValue([5,4])  ## 34

#r = Distortion("a b cc X__1 d ff X__2", "a cc b ff dd k X__1 X__2")
#print r.getValue([5,4])   ## 14

#r = Distortion("a b cc X__1 d ff X__2 ff ff", "a cc b ff dd k X__1 X__2")
#print r.getValue([5,4])  ## 26

#r = Distortion("a b cc X__1 d ff X__2 ff ff X__3", "a cc b ff dd k X__3 X__1 X__2")
#print r.getValue([5,4,6])  ## 38
