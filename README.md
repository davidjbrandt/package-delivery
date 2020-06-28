# Package Delivery
This is a Python project I wrote for a class on data structures and algorithms. The goal was to simulate a day of package deliveries and optimize (within reason) the number of miles driven to deliver all packages on time.

Some of the requirements which influenced design decisions were:
* Each block of code must have a comment explaining its function and time complexity in big O notation.
* A custom hash table must be implemented without using Python dictionaries to demonstrate an understanding of how they work.
* The fictional company this problem simulates has 3 trucks but only 2 drivers.
* The trucks travel an average of 18 mph, which includes delivery time, so deliveries can be treated as if they happen instantly.
* The trucks do not need to stop for gas.
* The trucks can only carry 16 packages at a time.