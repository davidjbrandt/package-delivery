class HashTable(object):
    # O(n) to initialize the underlying list. Length and load factor can be customized at instantiation
    # to minimize how often the hash table needs to resize.
    def __init__(self, length=16, load_factor=.75):
        self.array = [[] for _ in range(length)]
        self.load_factor = load_factor
        self.len = 0

    # Allows len() function to take this object as an argument.
    # Time complexity is O(1) because it keeps track of its own length when adding or removing elements.
    def __len__(self):
        return self.len

    # Allows retrieval using subscript syntax. O(1)
    def __getitem__(self, key):
        return self.get(key)

    # Allows adding elements using subscript syntax. O(1) amortized (see comment on add method)
    def __setitem__(self, key, value):
        self.add(key, value)

    # Allows removal of an element using del table[key] syntax. O(1)
    def __delitem__(self, key):
        self.remove(key)

    # Allows stored elements to be iterated in for each loop.
    # This method is O(1) though iteration itself is O(n).
    def __iter__(self):
        return HashTableIterator(self)

    # Allows use of the in keyword to test existence of key in hash table.
    # O(1) time complexity if there are few hash collisions
    def __contains__(self, key):
        index = self.hash(key)
        for kvp in self.array[index]:
            if kvp[0] == key:
                return True
        return False

    # Allows for the keys stored in the hash table to be iterated.
    # This method is O(1)
    def key_iterator(self):
        return HashKeyIterator(self)

    # Allows for the values stored in the hash table to be iterated.
    # This method is O(1)
    def value_iterator(self):
        return HashValueIterator(self)

    # Calculates the hash value used for the index of the underlying list. O(1)
    def hash(self, key):
        length = len(self.array)
        return hash(key) % length

    # Adds a key-value pair to the hash table, or replaces the value of an existing key.
    # This method runs in O(1) when resizing is not needed, which makes it O(1) amortized.
    # If the hash table is instantiated with appropriate length and load factor for the data set,
    # resizing will never be needed and this method will always run in O(1).
    def add(self, key, value):
        index = self.hash(key)
        done = False
        for kvp in self.array[index]:
            if kvp[0] == key:
                kvp[1] = value
                done = True
                break
        if not done:
            self.array[index].append([key, value])
            self.len += 1
        if self.is_full():
            self.double()

    # Removes a key-value pair from the hash table in O(1)
    def remove(self, key):
        index = self.hash(key)
        for i in range(len(self.array[index])):
            if self.array[index][i][0] == key:
                del self.array[index][i]
                self.len -= 1
                break

    # Retrieves the value stored under the given key in O(1)
    def get(self, key):
        index = self.hash(key)
        for kvp in self.array[index]:
            if kvp[0] == key:
                return kvp[1]
        raise KeyError()

    # Simultaneously removes a key-value pair and returns the value in O(1)
    def pop(self, key):
        index = self.hash(key)
        for i in range(len(self.array[index])):
            if self.array[index][i][0] == key:
                self.len -= 1
                return self.array[index].pop(i)[1]

    # Returns True if the number of items stored exceeds the load factor for the current length.
    # Runs in O(1)
    def is_full(self):
        return len(self) > len(self.array) * self.load_factor

    # Resizes the underlying list and copies the existing key-value pairs to the new list.
    # Runs in O(n)
    def double(self):
        new_ht = HashTable(len(self.array) * 2, self.load_factor)
        for kvp in self:
            new_ht.add(kvp[0], kvp[1])
        self.array = new_ht.array


class HashTableIterator(object):
    # O(1) to initialize dedicated iterator class
    def __init__(self, hash_table):
        self.outer = 0
        self.inner = 0
        self.ht = hash_table

    # Conforms to iterator protocol. Runs in O(1)
    def __iter__(self):
        return self

    # The outer loop steps through the list underlying the hash table while the inner loop
    # steps through each key-value pair stored at that index of the outer list. Since the
    # inner list returns immediately if a value is present, it is O(1). The outer list could
    # be considered O(n) in the sense that it might take longer to find the next value in a
    # sparsely populated HashTable, but in practice it finds the next value in O(1) if the length
    # of the list is appropriate for the amount of data in the HashTable.
    def __next__(self):
        while self.outer < len(self.ht.array):
            while self.inner < len(self.ht.array[self.outer]):
                next_kvp = self.ht.array[self.outer][self.inner]
                self.inner += 1
                return next_kvp
            self.outer += 1
            self.inner = 0
        raise StopIteration


class HashKeyIterator(object):
    # Provides an abstraction to iterate on the keys of the HashTable. O(1) to initialize.
    def __init__(self, hash_table):
        self.iterator = HashTableIterator(hash_table)

    # Conforms to iterator protocol. Runs in O(1)
    def __iter__(self):
        return self

    # Returns the key from the key-value pair returned by HashTableIterator.__next__() in O(1)
    def __next__(self):
        return self.iterator.__next__()[0]


class HashValueIterator(object):
    def __init__(self, hash_table):
        self.iterator = HashTableIterator(hash_table)

    # Conforms to iterator protocol. Runs in O(1)
    def __iter__(self):
        return self

    # Returns the value from the key-value pair returned by HashTableIterator.__next__() in O(1)
    def __next__(self):
        return self.iterator.__next__()[1]
