import numpy as np
import numpy.linalg
import scipy as sp
import scipy.spatial
import networkx as nx
import numpy.linalg
import polyhedron
import smoothener
import priorityQueue

class Voronizator:
    def __init__(self, sites=np.array([])):
        self._smoothener = smoothener.Smoothener()
        self._sites = sites
        self._shortestPath = np.array([])
        self._graph = nx.Graph()
        self._polyhedrons = []
        self._pathStart = np.array([])
        self._pathEnd = np.array([])

    def setCustomSites(self, sites):
        self._sites = sites
        
    def setRandomSites(self, number, seed=None):
        if seed != None:
            np.random.seed(0)
        self._sites = sp.rand(number,3)

    def addPolyhedron(self, polyhedron):
        self._polyhedrons.append(polyhedron)

    def addBoundingBox(self, a, b, maxEmptyArea=1, invisible=True):
        c = [a[0], b[1], a[2]]
        d = [b[0], a[1], a[2]]
        e = [a[0], a[1], b[2]]
        f = [b[0], b[1], a[2]]
        g = [b[0], a[1], b[2]]
        h = [a[0], b[1], b[2]]

        self._polyhedrons.append(polyhedron.Polyhedron(faces=np.array([
            [a,g,e],[a,d,g],[d,f,g],[f,b,g],[f,b,h],[f,h,c],
            [h,a,e],[h,c,a],[e,h,g],[h,b,g],[a,d,f],[a,f,c]
            ]), invisible=invisible, maxEmptyArea=maxEmptyArea))

    def setPolyhedronsSites(self):
        sites = []
        for polyhedron in self._polyhedrons:
            sites.extend(polyhedron.allPoints)

        self._sites = np.array(sites)
        
    def makeVoroGraph(self, prune=True):
        vor = sp.spatial.Voronoi(self._sites)
        vorVer = vor.vertices
        for ridge in vor.ridge_vertices:
            for i in range(len(ridge)):
                if (ridge[i] != -1) and (ridge[(i+1)%len(ridge)] != -1):
                    a = vorVer[ridge[i]]
                    b = vorVer[ridge[(i+1)%len(ridge)]]
                    if (not prune) or (not self._segmentIntersectPolyhedrons(a,b)):
                        self._graph.add_edge(tuple(a), tuple(b), weight=np.linalg.norm(a-b))
        i = 0
        for node in self._graph.nodes():
            self._graph.node[node]['index'] = i
            i = i + 1

    def calculateShortestPath(self, start, end, attachMode='near', prune=True, verbose=False, debug=False):
        if verbose:
            print('Attach start and end points', flush=True)
        if attachMode=='near':
            self._attachToGraphNear(start, end, prune)
        elif attachMode=='all':
            self._attachToGraphAll(start, end, prune)
        else:
            self._attachToGraphNear(start, end, prune)
            
        self._pathStart = start
        self._pathEnd = end

        if tuple(start) in self._graph.nodes():
            self._graph.node[tuple(start)]['index'] = 's'
        if tuple(end) in self._graph.nodes():
            self._graph.node[tuple(end)]['index'] = 'e'

        self._shortestPath = self._trijkstra(start, end, verbose, debug)
        
        # try:
        #     length,path=nx.bidirectional_dijkstra(self._graph, tuple(start), tuple(end))
        # except (nx.NetworkXNoPath, nx.NetworkXError):
        #     path = []
        #self._shortestPath = np.array(path)

    def plotSites(self, plotter):
        if self._sites.size > 0:
            plotter.plot(self._sites[:,0], self._sites[:,1], self._sites[:,2], 'o')

    def plotPolyhedrons(self, plotter):
        for poly in self._polyhedrons:
            poly.plot(plotter)
            
    def plotShortestPath(self, plotter):
        if self._shortestPath.size > 0:
            self._smoothener.plot(self._shortestPath, plotter)
        if self._pathStart.size > 0:
            plotter.plot([self._pathStart[0]], [self._pathStart[1]], [self._pathStart[2]], 'ro')
        if self._pathEnd.size > 0:
            plotter.plot([self._pathEnd[0]], [self._pathEnd[1]], [self._pathEnd[2]], 'ro')

    def plotGraph(self, plotter, vertexes=True, edges=True, labels=False, pathExtremes=False, showOnly=[]):
        if vertexes:
            for ver in self._graph.nodes():
                if not showOnly or self._graph.node[ver]['index'] in showOnly:
                    if (ver!=tuple(self._pathStart) and ver!=tuple(self._pathEnd)):
                        plotter.plot([ver[0]], [ver[1]], [ver[2]], 'og')
                        if labels and ('index' in self._graph.node[ver]):
                                plotter.text(ver[0], ver[1], ver[2], self._graph.node[ver]['index'], color='red')
                    elif pathExtremes==True:
                        plotter.plot([ver[0]], [ver[1]], [ver[2]], 'or')
                        if labels and ('index' in self._graph.node[ver]):
                                plotter.text(ver[0], ver[1], ver[2], self._graph.node[ver]['index'], color='red')

        if edges:
            for edge in self._graph.edges():
                if not showOnly or (self._graph.node[edge[0]]['index'] in showOnly and self._graph.node[edge[1]]['index'] in showOnly):
                    if pathExtremes==True or (edge[0]!=tuple(self._pathStart) and edge[0]!=tuple(self._pathEnd) and edge[1]!=tuple(self._pathStart) and edge[1]!=tuple(self._pathEnd)):
                        plotter.plot([edge[0][0], edge[1][0]], [edge[0][1], edge[1][1]], [edge[0][2], edge[1][2]], 'k--')

    def _segmentIntersectPolyhedrons(self, a, b):
        for polyhedron in self._polyhedrons:
            if polyhedron.intersectSegment(a,b)[0]:
                return True
        return False
                    
    def _triangleIntersectPolyhedrons(self, a, b, c):
        triangle = polyhedron.Polyhedron(faces=np.array([[a,b,c]]), distributePoints = False)
        intersect = False
        result = np.array([])
        for currPolyhedron in self._polyhedrons:
            currIntersect,currResult = currPolyhedron.intersectPathTriple(triangle)
            if currIntersect and (not intersect or (currResult[1] > result[1])):
                intersect = True
                result = currResult

        return (intersect, result)
                    
    def _attachToGraphNear(self, start, end, prune):
        firstS = True
        firstE = True
        minAttachS = None
        minAttachE = None
        minDistS = 0.
        minDistE = 0.
        for node in self._graph.nodes():
            if (not prune) or (not self._segmentIntersectPolyhedrons(start,np.array(node))):
                if firstS:
                    minAttachS = node
                    minDistS = np.linalg.norm(start-np.array(node))
                    firstS = False
                else:
                    currDist = np.linalg.norm(start-np.array(node))
                    if currDist < minDistS:
                        minAttachS = node
                        minDistS = currDist
                    
            if (not prune) or (not self._segmentIntersectPolyhedrons(end,np.array(node))):
                if firstE:
                    minAttachE = node
                    minDistE = np.linalg.norm(end-np.array(node))
                    firstE = False
                else:
                    currDist = np.linalg.norm(end-np.array(node))
                    if currDist < minDistE:
                        minAttachE = node
                        minDistE = currDist

        if minAttachS != None:
            self._graph.add_edge(tuple(start), minAttachS, weight=minDistS)
        if minAttachE != None:
            self._graph.add_edge(tuple(end), minAttachE, weight=minDistE)

    def _attachToGraphAll(self, start, end, prune):
        for node in self._graph.nodes():
            if (not prune) or (not self._segmentIntersectPolyhedrons(start,np.array(node))):
                self._graph.add_edge(tuple(start), node, weight=np.linalg.norm(start-np.array(node)))
            if (not prune) or (not self._segmentIntersectPolyhedrons(end,np.array(node))):
                self._graph.add_edge(tuple(end), node, weight=np.linalg.norm(end-np.array(node)))

    def _trijkstra(self, startA, endA, verbose, debug):
        start = tuple(startA)
        end = tuple(endA)
        endTriplet = (end,end,end) #special triplet for termination
        inf = float("inf")
        path = []
        Q = priorityQueue.PQueue()
        dist = {}
        prev = {}
        hits = []
        hitsRes = {}

        #create triplets
        if verbose:
            print('Create triplets ', end='', flush=True)

        if debug:
            hits_file = open("hits.txt","w")

        for node0 in self._graph.nodes():
            for node1 in self._graph.neighbors(node0):
                for node2 in filter(lambda node: node!=node0, self._graph.neighbors(node1)):
                    if verbose:
                        print('.', end='', flush=True)
                        
                    triplet = (node0,node1,node2)
                    if not triplet[::-1] in hits:
                        intersect,result = self._triangleIntersectPolyhedrons(np.array(node0), np.array(node1), np.array(node2))
                        if not intersect:
                            d = inf if (node0 != start) else 0
                            dist[triplet] = d
                            Q.add(triplet, d)
                        else:
                            if debug:
                                hits_file.write(str(triplet)+"\n")
                            hits[:0] = [triplet]
                            hitsRes[triplet] = result[1]

        if debug:
            hits_file.close()
        #modify collided triplets
        if verbose:
            print('', flush=True)        
            print('Modify collided triplets ', end='', flush=True)

        if debug:
            affectedT_file = open("affectedT.txt","w")
            unaffectedT_file = open("unaffectedT.txt","w")
            affunaffected_file = open("affunaffected.txt","w")
            affected_file = open("affected.txt","w")
            unaffected_file = open("unaffected.txt","w")
            hitsC_file = open("hitsC.txt","w")
            
        while len(hits) > 0:
            if verbose:
                print('.', end='', flush=True)
            hit = hits.pop()
            if debug:
                hitsC_file.write(str(hit)+'\n')
            a = hit[0]
            v = hit[1]
            b = hit[2]
            aa = np.array(a)
            va = np.array(v)
            ba = np.array(b)

            alpha = hitsRes[hit]
            a1a = (1.-alpha)*aa + alpha*va + 0.*ba
            b1a = 0.*aa + alpha*va + (1.-alpha)*ba
            a1 = tuple(a1a)
            b1 = tuple(b1a)

            #TODO: check why sometimes launch the exception
            try:
                self._graph.remove_edge(a,v)
                self._graph.remove_edge(v,b)
            except nx.exception.NetworkXError:
                pass
            self._graph.add_edge(a,a1, weight=np.linalg.norm(aa-a1a))
            self._graph.add_edge(a1,v, weight=np.linalg.norm(a1a-va))
            self._graph.add_edge(v,b1, weight=np.linalg.norm(va-b1a))
            self._graph.add_edge(b1,b, weight=np.linalg.norm(b1a-ba))

            #check if other triplets are affected
            for triplet in Q.filterGet(lambda tri: tri[0] == v or tri[2] == v):
                affected, newTriplet = self._modifyAffected(triplet, a, v, b, a1, b1)

                if affected:
                    if debug:
                        affectedT_file.write('a,v,b:'+str(a)+', '+str(v)+', '+str(b)+' - '+str(triplet)+' -> '+str(newTriplet)+'\n')
                    Q.remove(triplet)
                    d = inf if (newTriplet[0] != start) else 0
                    dist[newTriplet] = d
                    Q.add(newTriplet, d)
                else:
                    if debug:
                        unaffectedT_file.write('a,v,b:'+str(a)+', '+str(v)+', '+str(b)+' - '+str(triplet)+' -> '+str(newTriplet)+'\n')

            #check if other hits are affected (and if they are still hits)
            for tripletIndex,triplet in enumerate(hits):
                affected, newTriplet = self._modifyAffected(triplet, a, v, b, a1, b1)
                if debug:
                    affunaffected_file.write('a,v,b:'+str(a)+', '+str(v)+', '+str(b)+' - '+str(triplet)+' -> '+str(newTriplet)+'\n')
                
                if affected:
                    if debug:
                        affected_file.write('a,v,b:'+str(a)+', '+str(v)+', '+str(b)+' - '+str(triplet)+' -> '+str(newTriplet)+'\n')
                    intersect,result = self._triangleIntersectPolyhedrons(np.array(newTriplet[0]), np.array(newTriplet[1]), np.array(newTriplet[2]))
                    if not intersect:
                        d = inf if (node0 != start) else 0
                        dist[newTriplet] = d
                        Q.add(newTriplet, d)
                        hits.pop(tripletIndex)
                    else:
                        hits[tripletIndex] = newTriplet
                        hitsRes[newTriplet] = result[1]
                else:
                    if debug:
                        unaffected_file.write('a,v,b:'+str(a)+', '+str(v)+', '+str(b)+' - '+str(triplet)+' -> '+str(newTriplet)+'\n')

                
            for triplet in [(a,a1,v),(a1,v,b1),(v,b1,b),(b,b1,v),(b1,v,a1),(v,a1,a)]:
                d = inf if (triplet[0] != start) else 0
                dist[triplet] = d
                Q.add(triplet, d)

        if debug:
            affectedT_file.close()
            unaffectedT_file.close()
            affunaffected_file.close()
            affected_file.close()
            unaffected_file.close()
            hitsC_file.close()
        
        #add special ending triple
        dist[endTriplet] = inf
        Q.add(endTriplet, inf)

        if verbose:
            print('', flush=True)
            print('Dijkstra algorithm', end='', flush=True)
        try:
            while True:
                if verbose:
                    print('.',end='', flush=True)
                u = Q.pop()
                if u == endTriplet or dist[u] == inf:
                    break


                for v in Q.filterGet(lambda tri: u[1] == tri[0] and u[2] == tri[1]):
                    tmpDist = dist[u] + self._graph[u[0]][u[1]]['weight']
                    if tmpDist < dist[v]:
                        dist[v] = tmpDist
                        prev[v] = u
                        Q.add(v, tmpDist)

                if u[2] == end:
                    tmpDist = dist[u] + self._graph[u[0]][u[1]]['weight'] + self._graph[u[1]][u[2]]['weight']
                    if tmpDist < dist[endTriplet]:
                        dist[endTriplet] = tmpDist
                        prev[endTriplet] = u
                        Q.add(v, tmpDist)
        except KeyError:
            pass

        if verbose:
            print('', flush=True)
            print('Construct path', flush=True)
        
        u = endTriplet
        while u in prev:
            u = prev[u]
            path[:0] = [u[1]]
            
        if path:
            path[len(path):] = [end]
            path[:0] = [start]

        return np.array(path)

    def _modifyAffected(self, triplet, a, v, b, a1, b1):
        if triplet[1] == v and triplet[0] == a:
            newTriplet = (a1, v, triplet[2])
            affected = True
        elif triplet[1] == v and triplet[0] == b:
            newTriplet = (b1, v, triplet[2])
            affected = True
        elif triplet[1] == v and triplet[2] == a:
            newTriplet = (triplet[0], v, a1)
            affected = True
        elif triplet[1] == v and triplet[2] == b:
            newTriplet = (triplet[0], v, b1)
            affected = True
        elif triplet[0] == v and triplet[1] == a:
            newTriplet = (a1, a, triplet[2])
            affected = True
        elif triplet[0] == v and triplet[1] == b:
            newTriplet = (b1, b, triplet[2])
            affected = True
        elif triplet[2] == v and triplet[1] == a:
            newTriplet = (triplet[0], a, a1)
            affected = True
        elif triplet[2] == v and triplet[1] == b:
            newTriplet = (triplet[0], b, b1)
            affected = True
        else:
            affected = False
            newTriplet = ()

        return (affected, newTriplet)

    
