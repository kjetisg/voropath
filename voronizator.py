import numpy as np
import numpy.linalg
import scipy as sp
import scipy.spatial
import scipy.interpolate
import networkx as nx
import numpy.linalg
import polyhedron
import uuid

class Voronizator:
    def __init__(self, sites=np.array([]), bsplineDegree=4):
        self._sites = sites
        self._shortestPath = np.array([])
        self._graph = nx.Graph()
        self._tGraph = nx.DiGraph()
        self._startTriplet = None
        self._endTriplet = None
        self._polyhedrons = []
        self._pathStart = np.array([])
        self._pathEnd = np.array([])
        self._startId = uuid.uuid4()
        self._endId = uuid.uuid4()
        self._bsplineDegree = bsplineDegree

    def setBsplineDegree(self, bsplineDegree):
        self._bsplineDegree = bsplineDegree

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

    def makeVoroGraph(self, prune=True, verbose=True, debug=False):
        if verbose:
            print('Calculate Voronoi cells', flush=True)
        ids = {}
        vor = sp.spatial.Voronoi(self._sites)

        if verbose:
            print('Make pruned Graph from cell edges ', end='', flush=True)
            printDotBunch = 0
        vorVer = vor.vertices
        for ridge in vor.ridge_vertices:
            if verbose:
                if printDotBunch == 0:
                    print('.', end='', flush=True)
                printDotBunch = (printDotBunch+1)%10

            for i in range(1, len(ridge)):
                for j in range(i):
                    if (ridge[i] != -1) and (ridge[j] != -1):
                        a = vorVer[ridge[i]]
                        b = vorVer[ridge[j]]
                        if (not prune) or (not self._segmentIntersectPolyhedrons(a,b)):
                            if tuple(a) in ids.keys():
                                idA = ids[tuple(a)]
                            else:
                                idA = uuid.uuid4()
                                self._graph.add_node(idA, coord=a)
                                ids[tuple(a)] = idA

                            if tuple(b) in ids.keys():
                                idB = ids[tuple(b)]
                            else:
                                idB = uuid.uuid4()
                                self._graph.add_node(idB, coord=b)
                                ids[tuple(b)] = idB

                            self._graph.add_edge(idA, idB, weight=np.linalg.norm(a-b))

        if verbose:
            print('', flush=True)

        self._createTripleGraph(verbose, debug)

    def calculateShortestPath(self, start, end, attachMode='near', prune=True, postSimplify=True, verbose=False, debug=False):
        if verbose:
            print('Attach start and end points', flush=True)
        if attachMode=='near':
            self._attachToGraphNear(start, end, prune)
        elif attachMode=='all':
            self._attachToGraphAll(start, end, prune)
        else:
            self._attachToGraphNear(start, end, prune)

        self._attachSpecialStartEndTriples(verbose)

        self._pathStart = start
        self._pathEnd = end

        triPath = self._trijkstra(verbose, debug)
        self._shortestPath = self._extractPath(triPath, postSimplify, verbose, debug)

    def plotSites(self, plotter):
        if self._sites.size > 0:
            plotter.plot(self._sites[:,0], self._sites[:,1], self._sites[:,2], 'o')

    def plotPolyhedrons(self, plotter):
        for poly in self._polyhedrons:
            poly.plot(plotter)

    def plotShortestPath(self, plotter):
        if self._shortestPath.size > 0:
            x = self._shortestPath[:,0]
            y = self._shortestPath[:,1]
            z = self._shortestPath[:,2]

            t = range(len(self._shortestPath))
            ipl_t = np.linspace(0.0, len(self._shortestPath) - 1, 1000)
            #TODO: find a better way to substitute 100 above
            x_tup = sp.interpolate.splrep(t, x, k = self._bsplineDegree+1)
            y_tup = sp.interpolate.splrep(t, y, k = self._bsplineDegree+1)
            z_tup = sp.interpolate.splrep(t, z, k = self._bsplineDegree+1)

            x_list = list(x_tup)
            xl = x.tolist()
            x_list[1] = xl + [0.0, 0.0, 0.0, 0.0]

            y_list = list(y_tup)
            yl = y.tolist()
            y_list[1] = yl + [0.0, 0.0, 0.0, 0.0]

            z_list = list(z_tup)
            zl = z.tolist()
            z_list[1] = zl + [0.0, 0.0, 0.0, 0.0]

            x_i = sp.interpolate.splev(ipl_t, x_list)
            y_i = sp.interpolate.splev(ipl_t, y_list)
            z_i = sp.interpolate.splev(ipl_t, z_list)

            plotter.plot(x, y, z, 'r--')
            plotter.plot(x_i, y_i, z_i, 'r', lw=2)
            plotter.plot(x, y, z, 'ro')
        # if self._pathStart.size > 0:
        #     plotter.plot([self._pathStart[0]], [self._pathStart[1]], [self._pathStart[2]], 'ro')
        # if self._pathEnd.size > 0:
        #     plotter.plot([self._pathEnd[0]], [self._pathEnd[1]], [self._pathEnd[2]], 'ro')

    def plotGraph(self, plotter, vertexes=True, edges=True, labels=False, pathExtremes=False, showOnly=[]):
        if vertexes:
            for ver in self._graph.nodes():
                if not showOnly or ver in showOnly:
                    if (ver != self._startId and ver != self._endId):
                        plotter.plot([self._graph.node[ver]['coord'][0]], [self._graph.node[ver]['coord'][1]], [self._graph.node[ver]['coord'][2]], 'og')
                        if labels:
                                plotter.text(self._graph.node[ver]['coord'][0], self._graph.node[ver]['coord'][1], self._graph.node[ver]['coord'][2], ver, color='red')
                    elif pathExtremes==True:
                        plotter.plot([self._graph.node[ver]['coord'][0]], [self._graph.node[ver]['coord'][1]], [self._graph.node[ver]['coord'][2]], 'or')
                        if labels:
                                plotter.text(self._graph.node[ver]['coord'][0], self._graph.node[ver]['coord'][1], self._graph.node[ver]['coord'][2], ver, color='red')

        if edges:
            for edge in self._graph.edges():
                if not showOnly or (edge[0] in showOnly and edge[1] in showOnly):
                    if pathExtremes==True or (edge[0] != self._startId and edge[0] != self._endId and edge[1] != self._startId and edge[1] != self._endId):
                        plotter.plot([self._graph.node[edge[0]]['coord'][0], self._graph.node[edge[1]]['coord'][0]], [self._graph.node[edge[0]]['coord'][1], self._graph.node[edge[1]]['coord'][1]], [self._graph.node[edge[0]]['coord'][2], self._graph.node[edge[1]]['coord'][2]], 'k--')

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
        for node,nodeAttr in self._graph.node.items():
            if (not prune) or (not self._segmentIntersectPolyhedrons(start,nodeAttr['coord'])):
                if firstS:
                    minAttachS = node
                    minDistS = np.linalg.norm(start - nodeAttr['coord'])
                    firstS = False
                else:
                    currDist = np.linalg.norm(start - nodeAttr['coord'])
                    if currDist < minDistS:
                        minAttachS = node
                        minDistS = currDist

            if (not prune) or (not self._segmentIntersectPolyhedrons(end, nodeAttr['coord'])):
                if firstE:
                    minAttachE = node
                    minDistE = np.linalg.norm(end - nodeAttr['coord'])
                    firstE = False
                else:
                    currDist = np.linalg.norm(end - nodeAttr['coord'])
                    if currDist < minDistE:
                        minAttachE = node
                        minDistE = currDist

        if minAttachS != None:
            self._addNodeToTGraph(self._startId, start, minAttachS, minDistS, rightDirection=True)
        if minAttachE != None:
            self._addNodeToTGraph(self._endId, end, minAttachE, minDistE, rightDirection=False)

    def _attachToGraphAll(self, start, end, prune):
        for node,nodeAttr in self._graph.node.items():
            if (not prune) or (not self._segmentIntersectPolyhedrons(start, nodeAttr['coord'])):
                self._addNodeToTGraph(self._startId, start, node, np.linalg.norm(start - nodeAttr['coord']), rightDirection=True)
            if (not prune) or (not self._segmentIntersectPolyhedrons(end, nodeAttr['coord'])):
                self._addNodeToTGraph(self._endId, end, node, np.linalg.norm(end - nodeAttr['coord']), rightDirection=False)

    def _addNodeToTGraph(self, newId, coord, attachId, dist, rightDirection):
        self._graph.add_node(newId, coord=coord)
        self._graph.add_edge(newId, attachId, weight=dist)
        for otherId in filter(lambda node: node != newId, self._graph.neighbors(attachId)):
            newTriplet = uuid.uuid4()
            if rightDirection:
                self._tGraph.add_node(newTriplet, triplet=[newId,attachId,otherId])
                self._tGraph.add_edges_from([(newTriplet, otherTriplet, {'weight':dist}) for otherTriplet in self._tGraph.nodes() if self._tGraph.node[otherTriplet]['triplet'][0] == attachId  and self._tGraph.node[otherTriplet]['triplet'][1] == otherId])

            else:
                self._tGraph.add_node(newTriplet, triplet=[otherId,attachId,newId])
                self._tGraph.add_edges_from([(otherTriplet, newTriplet, {'weight':dist}) for otherTriplet in self._tGraph.nodes() if self._tGraph.node[otherTriplet]['triplet'][1] == otherId  and self._tGraph.node[otherTriplet]['triplet'][2] == attachId])

    def _attachSpecialStartEndTriples(self, verbose):
        #attach special starting and ending triplet
        if verbose:
            print('Create starting and ending triplets', flush=True)

        self._startTriplet = uuid.uuid4()
        self._endTriplet = uuid.uuid4()
        self._tGraph.add_node(self._startTriplet, triplet = [self._startId,self._startId,self._startId], hit = False)
        self._tGraph.add_node(self._endTriplet, triplet = [self._endId,self._endId,self._endId], hit = False)
        self._tGraph.add_edges_from([(self._startTriplet, n, {'weight':0.}) for n in self._tGraph.nodes() if self._tGraph.node[n]['triplet'][0] == self._startId])
        self._tGraph.add_edges_from([(n, self._endTriplet, {'weight':0.}) for n in self._tGraph.nodes() if self._tGraph.node[n]['triplet'][2] == self._endId])

    def _createTripleGraph(self, verbose, debug):
        #create triplets

        if debug:
            triplets_file = open("triplets.txt","w")

        if verbose:
            print('Create triplets ', end='', flush=True)
            printDotBunch = 0

        tripletIdList = {}
        def getUniqueId(triplet):
            if tuple(triplet) in tripletIdList.keys():
                tripletId = tripletIdList[tuple(triplet)]
            else:
                tripletId = uuid.uuid4()
                tripletIdList[tuple(triplet)] = tripletId
                self._tGraph.add_node(tripletId, triplet = triplet)
            return tripletId

        for edge in self._graph.edges():
            if verbose:
                if printDotBunch == 0:
                    print('.', end='', flush=True)
                printDotBunch = (printDotBunch+1)%10


            tripletsSxOutgoing = []
            tripletsSxIngoing = []
            tripletsDxOutgoing = []
            tripletsDxIngoing = []

            for nodeSx in filter(lambda node: node != edge[1], self._graph.neighbors(edge[0])):
                tripletId = getUniqueId([nodeSx,edge[0],edge[1]])
                tripletsSxOutgoing.append(tripletId)
                if debug:
                    triplets_file.write('SxO: {}\n'.format(self._tGraph.node[tripletId]['triplet']))

                tripletId = getUniqueId([edge[1],edge[0],nodeSx])
                tripletsSxIngoing.append(tripletId)
                if debug:
                    triplets_file.write('SxI: {}\n'.format(self._tGraph.node[tripletId]['triplet']))

            for nodeDx in filter(lambda node: node != edge[0], self._graph.neighbors(edge[1])):
                tripletId = getUniqueId([nodeDx,edge[1],edge[0]])
                tripletsDxOutgoing.append(tripletId)
                if debug:
                    triplets_file.write('DxO: {}\n'.format(self._tGraph.node[tripletId]['triplet']))

                tripletId = getUniqueId([edge[0],edge[1],nodeDx])
                tripletsDxIngoing.append(tripletId)
                if debug:
                    triplets_file.write('DxI: {}\n'.format(self._tGraph.node[tripletId]['triplet']))

            for tripletSx in tripletsSxOutgoing:
                for tripletDx in tripletsDxIngoing:
                    self._tGraph.add_edge(tripletSx, tripletDx, {'weight':self._graph.edge[self._tGraph.node[tripletSx]['triplet'][0]][self._tGraph.node[tripletDx]['triplet'][0]]['weight']})

            for tripletDx in tripletsDxOutgoing:
                for tripletSx in tripletsSxIngoing:
                    self._tGraph.add_edge(tripletDx, tripletSx, {'weight':self._graph.edge[self._tGraph.node[tripletDx]['triplet'][0]][self._tGraph.node[tripletSx]['triplet'][0]]['weight']})

        if verbose:
            print('', flush=True)

        if debug:
            triplets_file.close()


    def _trijkstra(self, verbose, debug):
        try:
            if verbose:
                print('Dijkstra algorithm', flush=True)

            length,triPath=nx.bidirectional_dijkstra(self._tGraph, self._startTriplet, self._endTriplet)


        except (nx.NetworkXNoPath, nx.NetworkXError):
            print('ERROR: Impossible to find a path')
            triPath = []

        return triPath

    def _extractPath(self, triPath, postSimplify, verbose, debug):
        if verbose:
            print('Adjust hits and construct path', flush=True)

        path = []
        for i,t in [(i,t) for i,t in enumerate(triPath)]:
            if(t == self._startTriplet):
                path.append(self._graph.node[self._startId]['coord'])
            elif(t == self._endTriplet):
                path.append(self._graph.node[self._endId]['coord'])
            else:
                a = self._tGraph.node[t]['triplet'][0]
                v = self._tGraph.node[t]['triplet'][1]
                b = self._tGraph.node[t]['triplet'][2]

                intersect,intersectRes = self._triangleIntersectPolyhedrons(self._graph.node[a]['coord'], self._graph.node[v]['coord'], self._graph.node[b]['coord'])
                if intersect:
                    alpha = intersectRes[1]
                    #adjust graph
                    #a1,b1 for avoiding obstacle
                    #a2,b2 for augmenting grade
                    a1 = uuid.uuid4()
                    b1 = uuid.uuid4()

                    self._graph.add_node(a1, coord = (1.-alpha)*self._graph.node[a]['coord'] + alpha*self._graph.node[v]['coord'])
                    self._graph.add_node(b1, coord = alpha*self._graph.node[v]['coord'] + (1.-alpha)*self._graph.node[b]['coord'])

                    self._graph.remove_edge(a,v)
                    self._graph.remove_edge(v,b)

                    if self._bsplineDegree <= 2:
                        self._graph.add_edge(a,a1, weight=np.linalg.norm(self._graph.node[a]['coord'] - self._graph.node[a1]['coord']))
                        self._graph.add_edge(a1,v, weight=np.linalg.norm(self._graph.node[a1]['coord'] - self._graph.node[v]['coord']))
                        self._graph.add_edge(v,b1, weight=np.linalg.norm(self._graph.node[v]['coord'] - self._graph.node[b1]['coord']))
                        self._graph.add_edge(b1,b, weight=np.linalg.norm(self._graph.node[b1]['coord'] - self._graph.node[b]['coord']))

                        path.append(self._graph.node[a1]['coord'])
                        path.append(self._graph.node[v]['coord'])
                        path.append(self._graph.node[b1]['coord'])

                    elif self._bsplineDegree == 4:
                        a2 = uuid.uuid4()
                        b2 = uuid.uuid4()
                        self._graph.add_node(a2, coord = 0.25*self._graph.node[a1]['coord'] + 0.75*self._graph.node[v]['coord'])
                        self._graph.add_node(b2, coord = 0.25*self._graph.node[b1]['coord'] + 0.75*self._graph.node[v]['coord'])

                        self._graph.add_edge(a,a1, weight=np.linalg.norm(self._graph.node[a]['coord'] - self._graph.node[a1]['coord']))
                        self._graph.add_edge(a1,a2, weight=np.linalg.norm(self._graph.node[a1]['coord'] - self._graph.node[a2]['coord']))
                        self._graph.add_edge(a2,v, weight=np.linalg.norm(self._graph.node[a2]['coord'] - self._graph.node[v]['coord']))
                        self._graph.add_edge(v,b2, weight=np.linalg.norm(self._graph.node[v]['coord'] - self._graph.node[b2]['coord']))
                        self._graph.add_edge(b2,b1, weight=np.linalg.norm(self._graph.node[b2]['coord'] - self._graph.node[b1]['coord']))
                        self._graph.add_edge(b1,b, weight=np.linalg.norm(self._graph.node[b1]['coord'] - self._graph.node[b]['coord']))

                        path.append(self._graph.node[a1]['coord'])
                        path.append(self._graph.node[a2]['coord'])
                        path.append(self._graph.node[v]['coord'])
                        path.append(self._graph.node[b2]['coord'])
                        path.append(self._graph.node[b1]['coord'])

                    #adjust next triple
                    if i < len(triPath)-1:
                        self._tGraph.node[triPath[i+1]]['triplet'][0] = b1

                else:
                    if postSimplify:
                        #delete triple
                        if i < len(triPath)-1:
                            self._tGraph.node[triPath[i+1]]['triplet'][0] = a
                            self._graph.add_edge(a,self._tGraph.node[triPath[i+1]]['triplet'][1], weight=np.linalg.norm(self._graph.node[a]['coord'] - self._graph.node[self._tGraph.node[triPath[i+1]]['triplet'][1]]['coord']))

                    else:
                        if self._bsplineDegree <= 2:
                            path.append(self._graph.node[v]['coord'])
                        elif self._bsplineDegree == 4:
                            #a1,b1 for augmenting grade
                            a1 = uuid.uuid4()
                            b1 = uuid.uuid4()

                            self._graph.add_node(a1, coord = 0.25*self._graph.node[a]['coord'] + 0.75*self._graph.node[v]['coord'])
                            self._graph.add_node(b1, coord = 0.25*self._graph.node[b]['coord'] + 0.75*self._graph.node[v]['coord'])

                            self._graph.remove_edge(a,v)
                            self._graph.remove_edge(v,b)

                            self._graph.add_edge(a,a1, weight=np.linalg.norm(self._graph.node[a]['coord'] - self._graph.node[a1]['coord']))
                            self._graph.add_edge(a1,v, weight=np.linalg.norm(self._graph.node[a1]['coord'] - self._graph.node[v]['coord']))
                            self._graph.add_edge(v,b1, weight=np.linalg.norm(self._graph.node[v]['coord'] - self._graph.node[b1]['coord']))
                            self._graph.add_edge(b1,b, weight=np.linalg.norm(self._graph.node[b1]['coord'] - self._graph.node[b]['coord']))

                            #adjust next triple
                            if i < len(triPath)-1:
                                self._tGraph.node[triPath[i+1]]['triplet'][0] = b1

                            path.append(self._graph.node[a1]['coord'])
                            path.append(self._graph.node[v]['coord'])
                            path.append(self._graph.node[b1]['coord'])

        #path = [self._graph.node[self._tGraph.node[n]['triplet'][1]]['coord'] for n in triPath]
        return np.array(path)
