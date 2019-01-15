from copy import deepcopy
from queue import Queue


class NetworkGraph:
    '''
    description: defines a directed graph in which the nodes are the networks in the service area and the an edge between
    nodes x and y represent that possibility of a user moving from network x to network y in one 'hop' (i.e. without passing
    via an intermediary node
    '''

    def __init__(self, vertexList=[], edgeList=[]):
        self.vertices = vertexList
        self.edges = edgeList
        self.adjacentVertexList = []  # to store set of vertices that can be reached from each vertex
        NetworkGraph.computeAdjacentVertices(self)
        # end __init__

    def addVertex(self, vertex):
        self.vertices.append(vertex)
        self.adjacentVertexList.append(set())
        # end addVertex

    def removeVertex(self, vertex):
        # remove all edges with the vertex...
        if vertex in self.vertices:
            for edge in self.edges[::-1]:  # in reverse order; because items are being deleting from the list
                if edge.sourceVertex == vertex or edge.destinationVertex == vertex: self.edges.remove(edge)
            # delete its set of adjacent vertices
            vertexIndex = self.vertices.index(vertex)
            self.adjacentVertexList.pop(vertexIndex)
            self.vertices.remove(vertex)  # remove the vertex from vertex list
            return True  # for success
        return False  # for failure
        # end removeVertex

    def addEdge(self, sourceVertex, destinationVertex, userList=[]):
        self.edges.append(Edge(sourceVertex, destinationVertex, userList))

        # update the adjacency list
        vertexIndex = self.vertices.index(
            sourceVertex)  # get index of the source vertex; its adjacency list to be updated will be at the same index
        self.adjacentVertexList[vertexIndex].add(destinationVertex)
        # end addEdge

    def removeEdge(self, sourceVertex, destinationVertex):
        for edge in self.edges:
            if edge.sourceVertex == sourceVertex and edge.destinationVertex == destinationVertex:
                self.edges.remove(edge)

                # update the adjacency list
                vertexIndex = self.vertices.index(sourceVertex)
                self.adjacentVertexList[vertexIndex].remove(destinationVertex)
                return True  # for success
        return False  # for failure
        # end removeEdge

    def edgeExist(self, sourceVertex, destinationVertex):
        '''
        desc: checks if an edge exists between sourceVertex and destinationVertex
        '''
        for edge in self.edges:
            if edge.sourceVertex == sourceVertex and edge.destinationVertex == destinationVertex:
                return True
        return False
        # end edgeExist

    def addUserToEdge(self, sourceVertex, destinationVertex, userID):
        for edge in self.edges:
            if edge.sourceVertex == sourceVertex and edge.destinationVertex == destinationVertex:
                edge.addUser(userID)
                return True  # for success
        return False  # for failure
        # end addUserToEdge

    def removeUserFromEdge(self, sourceVertex, destinationVertex, userID):
        userFoundRemoved = False

        for edge in self.edges[::-1]:
            if edge.sourceVertex == sourceVertex and userID in edge.userList:  # must actually remove the user from other edges too
                edge.removeUser(userID)
                if len(edge.userList) == 0:
                    NetworkGraph.removeEdge(self, edge.sourceVertex,
                                            edge.destinationVertex)  # if the user list becomes zero (no user can move along this path), delete the edge
                userFoundRemoved = True
        return userFoundRemoved  # for success or failure
        # end removeUserFromEdge

    def computeAdjacentVertices(self):
        ''' desc: computes list of vertices that can be reached from the current vertex '''
        for i in range(len(self.vertices)):
            adjacentVerticesSet = set()
            self.adjacentVertexList.append(adjacentVerticesSet)

        for edge in self.edges:
            vertexIndex = self.vertices.index(edge.sourceVertex)
            self.adjacentVertexList[vertexIndex].add(edge.destinationVertex)
            # end computeAdjacentVertices

    def shortestPath(self, sourceVertex, destinationVertex):
        '''
        desc: runs BFS to get the path with the least no of edges connecting the 2 networks
        param: ID of 2 networks
        returns: least no of edges to be traversed to get from one network to the other
        '''
        queue = Queue();
        unvisitedVertices = set(self.vertices)  # set of vertices not visited yet
        pathLength = [-1] * len(self.vertices)  # parent vertex of current vertex
        path = [[]] * len(self.vertices)  # path to current vertex

        queue.put(sourceVertex)
        unvisitedVertices.remove(sourceVertex)

        sourceVertexIndex = self.vertices.index(sourceVertex)
        pathLength[sourceVertexIndex] = 0  # distance to source vertex set to 0
        neighbour = -1
        while (queue.empty() == False and neighbour != destinationVertex):  # while the queue is not empty
            # remove the head of queue
            head = queue.get()
            headVertexIndex = self.vertices.index(head)

            # mark and enqueue all unvisited neighbours of u
            neighbourList = self.adjacentVertexList[headVertexIndex]  # get neighbours of head
            for neighbour in neighbourList:
                if neighbour in unvisitedVertices:
                    unvisitedVertices.remove(neighbour)
                    queue.put(neighbour)
                    neighbourVertexIndex = self.vertices.index(neighbour)
                    pathLength[neighbourVertexIndex] = pathLength[headVertexIndex] + 1
                    path[neighbourVertexIndex] = deepcopy(path[headVertexIndex])
                    path[neighbourVertexIndex].append(head)
                if neighbour == destinationVertex:
                    path[neighbourVertexIndex].append(neighbour)
                    break

        destinationVertexIndex = self.vertices.index(destinationVertex)
        return pathLength[destinationVertexIndex], path[destinationVertexIndex]
        # end shortestPath

    def __str__(self):
        edgeList = ""
        for edge in self.edges:
            edgeList += "\n\t" + Edge.__str__(edge)
        return "Vertices: " + str(self.vertices) + "\nEdges: " + edgeList + "\nAdjacency list: " + str(
            self.adjacentVertexList)
        # end __str__


class Edge:
    '''
    description: defines an edge between 2 networks, representing the possibility of users to move from the first to the second
    '''

    def __init__(self, fromVertex=-1, toVertex=-1, user=[]):
        self.sourceVertex = fromVertex
        self.destinationVertex = toVertex
        self.userList = user  # user who can move from sourceVertex to destination vertex
        # sort the list of users in ascending oder of number of networks available to them; done in the program using the class instead...
        # end __init__

    def addUser(self, userID):
        self.userList.append(userID)
        # sort the list of users in ascending oder of number of networks available to them
        # end addUser

    def removeUser(self, userID):
        self.userList.remove(userID)
        # end removeUser

    def __str__(self):
        return "(" + str(self.sourceVertex) + ", " + str(self.destinationVertex) + ") ----- " + str(self.userList)
        # end __str__
