from containers import HashTable
from datetime import time, timedelta, datetime, date


class Clock(object):
    # This class provides an interface for the simulation to track time throughout the day. The date
    # component exists only because the timedelta operates on a datetime but not a time.
    # Initializes in O(1)
    def __init__(self, start_time, increment):
        self.dummy_date = date.today()
        self.start_time = start_time
        self.current_datetime = datetime.combine(self.dummy_date, self.start_time)
        self.increment = increment

    # Advances time by the set increment. O(1)
    def advance_time(self):
        self.current_datetime += self.increment

    # Returns current time on clock. O(1)
    def now(self):
        return self.current_datetime.time()

    # Adds given number of time increments and returns what the time will be after they pass. O(1)
    def time_after_increments(self, increments):
        return (self.current_datetime + (increments * self.increment)).time()


class Location(object):
    # This class represents locations to which the trucks can drive and also holds
    # address information for packages. Initializes in O(1).
    def __init__(self, location_id, address, city, zip_code, distances):
        self.location_id = location_id
        self.address = address
        self.city = city
        self.zip_code = zip_code
        self.distances = distances

    # Part of the visitor pattern; when trucks arrive at a location they call this method and
    # most locations will in turn tell the truck to deliver packages. Calls the deliver method
    # in O(1), but that really means it has the same time complexity as the deliver method (See
    # notes there)
    def arrive(self, truck):
        truck.deliver()

    # This method looks up the distance to the other location in the distance table. O(1)
    def distance_to(self, other):
        row = max(self.location_id, other.location_id)
        col = min(self.location_id, other.location_id)
        return self.distances[row][col]


class Hub(Location):
    # This class inherits Location because it is a special type of location. Initializes in O(1)
    def __init__(self, location_id, address, city, zip_code, distances, all_packages, clock):
        super().__init__(location_id, address, city, zip_code, distances)
        self.all_packages = all_packages
        self.clock = clock
        self.remaining_packages = HashTable()
        self.priority_packages = HashTable()
        self.delayed_packages = HashTable()
        self.undeliverable_packages = HashTable()
        self.truck2_only_packages = HashTable()
        self.deliver_with = HashTable()
        self.packages_by_location = HashTable()
        self.packages_by_deadline = HashTable()
        self.deadlines = []

    # This method is called to set up package sorting information after the packages have been added
    # to self.all_packages. Runs in O(n).
    def sort_packages(self):
        for package in self.all_packages.value_iterator():
            self.remaining_packages.add(package.package_id, package)
            if package.deadline != "EOD":
                self.priority_packages.add(package.package_id, package)
            if package.status == "Delayed":
                self.delayed_packages.add(package.package_id, package)
            if package.status == "Undeliverable":
                self.undeliverable_packages.add(package.package_id, package)
            if package.truck2_only:
                self.truck2_only_packages.add(package.package_id, package)
            if package.package_id not in self.deliver_with:
                self.deliver_with.add(package.package_id, [])
            # This part is what allows the group_packages method to work. Each package that must be delivered
            # with another package is indexed in both directions so that if the program tries loading either
            # package, the other(s) will be included if there is room on the truck or the whole group will not
            # be loaded if there is not room for all packages in the group or if there is a problem with any
            # package in the group.
            for other_package_id in package.deliver_with:
                if other_package_id in self.deliver_with:
                    self.deliver_with[other_package_id].append(package)
                else:
                    self.deliver_with.add(other_package_id, [package])
                self.deliver_with[package.package_id].append(self.all_packages[other_package_id])
            location = package.delivery_location
            if location.location_id in self.packages_by_location:
                self.packages_by_location[location.location_id].append(package)
            else:
                self.packages_by_location.add(location.location_id, [package])
            # This part indexes the packages by deadline and establishes a list of deadlines in ascending
            # order to allow for a faster compilation of packages sorted in order of deadline later.
            if package.deadline_time in self.packages_by_deadline:
                self.packages_by_deadline[package.deadline_time].append(package)
            else:
                self.packages_by_deadline[package.deadline_time] = [package]
                self.deadlines.append(package.deadline_time)
                self.deadlines.sort()

    # Part of the visitor pattern; when trucks arrive at a location they call this method on it.
    # For most locations this prompts the trucks to deliver packages, but when arriving at the hub
    # the next batch of packages is loaded instead. The loop runs in O(n), but determining the packages
    # in the list is the real bottleneck of this method and it runs before the loop, therefore the method
    # has the same time complexity as self.next_batch(), which is O(n^3).
    def arrive(self, truck):
        next_batch = self.next_batch(truck)
        if len(next_batch) == 0:
            truck.wait_at_hub()
        for package in next_batch:
            truck.add_package(package)

    # Selects the next batch of packages to be loaded onto the given truck. First, a list of all packages
    # eligible to be in the batch is retrieved, sorted first by deadline then by nearest next delivery, an
    # operation that runs in O(n^2). Then, add_grouped_packages, which runs in O(n^2) relative to the size of
    # the group, is called until the truck is at capacity or the list of eligible packages is exhausted. As
    # part of that method call, any additional packages going to the same location as one of the packages in
    # each group will be passed recursively to the add_grouped_packages method, but this does not increase the
    # total time complexity of this method because, practically, it has the same effect as moving those packages
    # earlier in the list of packages being iterated in this method. Meanwhile, as soon as the truck is loaded
    # to capacity, all loops break and the method finishes by calling the O(n^2) operation fix_late_deliveries().
    # Since looping through the packages is O(n) and each iteration is O(n^2), this puts the final time complexity
    # at O(n^3), but it is worth noting that larger groups (the n^2) will likely result in fewer iterations as
    # they load the truck to capacity faster.
    def next_batch(self, truck):
        packages = []
        for priority_package in self.highest_priority_packages(truck.truck_id):
            self.add_grouped_packages(priority_package, packages, truck)
            if len(packages) == truck.capacity:
                break
        return self.fix_late_deliveries(packages)

    # Attempts to order packages by shortest path and checks if route will result in late deliveries, in
    # which case the packages with earlier deadlines are left near the beginning of the list. O(n^2) due
    # to use of sort_by_location method.
    def fix_late_deliveries(self, packages):
        on_time_packages = sort_by_location(packages, self)
        if self.has_late_delivery(on_time_packages):
            on_time_packages = []
            packages_to_reorder = []
            last_priority_index = 0
            for i in range(len(packages)):
                if packages[i].deadline != "EOD":
                    last_priority_index = i
            for i in range(len(packages)):
                if i <= last_priority_index:
                    on_time_packages.append(packages[i])
                else:
                    packages_to_reorder.append(packages[i])
            for package in sort_by_location(packages_to_reorder, packages[last_priority_index].delivery_location):
                on_time_packages.append(package)
        return on_time_packages

    # Searches through package list while tracking mileage looking for late deliveries. Runs in O(n).
    def has_late_delivery(self, packages):
        total_distance = 0
        last_location = self
        late = False
        for package in packages:
            location = package.delivery_location
            total_distance += int(10 * location.distance_to(last_location))
            last_location = location
            if self.clock.time_after_increments(total_distance) > package.deadline_time:
                late = True
                break
        return late

    # This method adds packages first from any group which must be delivered together per requirements,
    # then attempts to add any remaining packages with the same address as a package from the group.
    # Runs in O(n^2) worst case for the base algorithm, but recursive calls can add some complexity.
    # See notes on next_batch() for more detail on the effects of this recursion.
    def add_grouped_packages(self, first_package, batch, truck):
        group = HashTable()
        # O(n^2) method call
        is_eligible = self.group_packages(first_package, group, truck.truck_id)
        if is_eligible and len(group) + len(batch) <= truck.capacity:
            # O(n) loop
            for package in group.value_iterator():
                self.add_to_batch(package, batch, truck)
            self.add_packages_by_locations(package_locations(group.value_iterator()), batch, truck)

    # This method adds any eligible packages from a HashTable of locations and breaks early if the truck is full.
    # Although it may appear that this is O(n^2) because of nested loops, the actual time complexity of this
    # operation depends solely on the number of total packages regardless of how many locations these packages
    # are delivered to. For example, if there are 5 packages at one location, the loop selecting the location runs
    # once and the inner loop selecting the package runs 5 times, whereas if the same number of packages were instead
    # spread over 3 locations, inner loop still runs the same 5 times. Therefore, this method runs in O(n).
    def add_packages_by_locations(self, locations, batch, truck):
        for location in locations.value_iterator():
            if len(batch) == truck.capacity:
                break
            self.add_packages_by_location(location, batch, truck)

    # This method adds any eligible packages at a given location to the current batch of packages and breaks
    # early when the truck is full. It calls add_grouped_packages to ensure that any package added to the truck
    # also includes any packages which are required to be delivered with it. Base method runs in O(n), but
    # recursion can change the total complexity. See notes on next_batch() for more detail.
    def add_packages_by_location(self, location, batch, truck):
        for package in self.packages_by_location[location.location_id]:
            if len(batch) == truck.capacity:
                break
            self.add_grouped_packages(package, batch, truck)

    # This method prevents too many packages from being loaded onto the truck and ensures that
    # the appropriate HashTables tracking package status are updated if the package is loaded.
    # Runs in O(1).
    def add_to_batch(self, package, batch, truck):
        if len(batch) < truck.capacity and self.is_eligible_package(package, truck.truck_id):
            batch.append(package)
            self.remaining_packages.remove(package.package_id)
            if package.package_id in self.priority_packages:
                self.priority_packages.remove(package.package_id)

    # This method recursively adds all packages that must be delivered together (per special instructions,
    # not necessarily packages with the same address) into the provided HashTable. Since it is a HashTable,
    # testing with "not in" is O(1) and when the condition is False it aborts that iteration immediately.
    # Adding to the HashTable is also O(1). The initial condition will pass exactly n times where n is the
    # final size of the group as long as it is not cut short by one of the packages in the group being ineligible,
    # so the best case runs in linear time. However, the absolute worst case would be if each of the n packages
    # specifically lists each of the n-1 other packages in its requirements, causing an n-1 loop to run n times.
    # n(n-1) is n^2 - n, or O(n^2).
    def group_packages(self, package, hash_group, truck_id):
        is_eligible = self.is_eligible_package(package, truck_id)
        if is_eligible and package.package_id not in hash_group:
            hash_group.add(package.package_id, package)
            for other_package in self.deliver_with[package.package_id]:
                is_eligible = is_eligible and self.group_packages(other_package, hash_group, truck_id)
        return is_eligible

    # This method tests whether a given package is eligible to be loaded onto a given truck.
    # All tests using in are done with HashTables, therefore this runs in O(1).
    def is_eligible_package(self, package, truck_id):
        package_id = package.package_id
        is_eligible = package_id in self.remaining_packages and package_id not in self.undeliverable_packages
        is_eligible = is_eligible and package_id not in self.delayed_packages
        is_eligible = is_eligible and (not package.truck2_only or truck_id == 2)
        return is_eligible

    # This method returns a list of all packages eligible for loading onto the truck sorted first by
    # deadline time, then approximately in order of the nearest next delivery location. The last package
    # in each deadline group is preserved as the starting location for the next round to promote clustering
    # packages with nearby delivery locations while also giving priority to packages with the earliest
    # deadlines. The outer loop and the first inner loop actually combine for O(n) runtime because the number
    # of packages in each deadline varies, but the operations scale only by the number of total packages.
    # The second inner loop also runs in O(n), but first it sorts the eligible packages by location, which is
    # O(n^2). That makes the entire method O(n^2).
    def highest_priority_packages(self, truck_id):
        packages = []
        last_location = self
        for deadline in self.deadlines:
            deadline_packages = []
            for package in self.packages_by_deadline[deadline]:
                if self.is_eligible_package(package, truck_id):
                    deadline_packages.append(package)
            for package in sort_by_location(deadline_packages, last_location):
                packages.append(package)
                last_location = package.delivery_location
        return packages


# This method returns a list of the given packages in order by delivery location matching the
# location order returned by the shortest path method. That method is O(n^2) but runs only once
# in this method. These locations are iterated first because there may be more than one package
# for each location, resulting in fewer iterations of the package list. However, in the worst case
# the number of locations is equal to the number of packages, causing n^2 iterations. Therefore,
# shortest path's O(n^2) + n^2 iterations is still O(n^2).
def sort_by_location(packages, starting_location):
    sorted_packages = []
    for location in shortest_path(package_locations(packages), starting_location):
        for package in packages:
            if package.delivery_location == location:
                sorted_packages.append(package)
    return sorted_packages


# This method will take a HashTable of locations and find the shortest distance from the
# starting point (the hub), then find the shortest distance from that location to the remaining locations,
# and so on until all locations have been visited. The while loop runs n times and the inner for loop runs
# at most n times. Therefore, it runs in O(n^2).
def shortest_path(locations, starting_location):
    sorted_locations = []
    last_location = starting_location
    while len(locations) != 0:
        next_location = None
        shortest_distance = 9999.9
        for location in locations.value_iterator():
            if last_location.distance_to(location) < shortest_distance:
                shortest_distance = last_location.distance_to(location)
                next_location = location
        locations.remove(next_location.location_id)
        sorted_locations.append(next_location)
        last_location = next_location
    return sorted_locations


# This method extracts package delivery locations into a HashTable, which prevents duplicates from
# being added. Runs in O(n).
def package_locations(packages):
    locations = HashTable()
    for package in packages:
        location = package.delivery_location
        locations.add(location.location_id, location)
    return locations


class Simulator(object):
    # This class contains the main control elements to simulate the day's deliveries. Initializes in O(1)
    def __init__(self, hub, trucks, clock, locations, stop_at):
        self.hub = hub
        self.trucks = trucks
        self.clock = clock
        self.locations = locations
        self.stop_at = stop_at

    # Main control loop goes here. As such, the time complexity is technically the same as the entire
    # program, which would be O(n^3). Apart from the "while not finished" loop, this method runs in O(n)
    # based on the number of trucks.
    def run(self):
        self.hub.sort_packages()
        self.hub.arrive(self.trucks[0])
        self.hub.arrive(self.trucks[1])
        while not self.is_finished() and self.clock.now() < self.stop_at:
            self.advance_time()
        print_status(self.hub.all_packages.value_iterator(), self.clock, self.trucks)
        if self.clock.now() < self.stop_at:
            print("Finished at " + str(self.clock.now()))

    # This method is O(n) where n is the number of trucks, but the drive method can trigger other
    # more complex algorithms when the trucks arrive at their destinations.
    def advance_time(self):
        self.clock.advance_time()
        self.check_events()
        for truck in self.trucks:
            truck.drive()

    # Defines the finish condition for the simulation. Runs in O(n) worst case where n is the
    # number of trucks.
    def is_finished(self):
        finished = len(self.hub.remaining_packages) == 0
        if finished:
            for truck in self.trucks:
                finished = len(truck.packages) == 0
                if not finished:
                    break
        return finished

    # This method initiates time-based events during the simulation. The loops that sometimes run
    # during this method are O(n).
    def check_events(self):
        now = self.clock.now()
        # This is the delayed packages arriving to the hub at 9:05
        if now == time(9, 5, 0):
            for package in self.hub.delayed_packages.value_iterator():
                package.status = "At Package Hub"
            self.hub.delayed_packages = HashTable()
        # This is the address correction for the undeliverable package
        if now == time(10, 20, 0):
            undeliverable_package = self.hub.all_packages[9]
            for location in self.locations:
                if location.address == "410 S State St":
                    undeliverable_package.delivery_location = location
                    undeliverable_package.status = "At Package Hub"
                    self.hub.undeliverable_packages.remove(undeliverable_package.package_id)
                    break


class Package(object):
    # This class represents a package to be delivered. Initializes in O(1)
    def __init__(self, package_id, delivery_location, weight, deadline, status, truck2_only, deliver_with):
        self.package_id = package_id
        self.delivery_location = delivery_location
        self.weight = weight
        self.deadline = deadline
        self.status = status
        self.truck2_only = truck2_only
        self.deliver_with = deliver_with
        # This part assigns a datetime.time based on the deadline string
        if self.deadline == "EOD":
            self.deadline_time = time(17, 0, 0)
        else:
            hour = int(deadline[:deadline.find(":")])
            minute = int(deadline[deadline.find(":") + 1:deadline.find(" ")])
            time_of_day = deadline[deadline.find(" ") + 1:]
            if hour != 12 and time_of_day == "PM":
                hour += 12
            if hour == 12 and time_of_day == "AM":
                hour = 0
            self.deadline_time = time(hour, minute, 0)

    # This prints the package attributes and delivery status. O(1)
    def print_status(self):
        pid = pad_spaces(str(self.package_id), 10, True)
        location = self.delivery_location
        address = location.address
        city = location.city
        zip_code = location.zip_code
        location_str = pad_spaces(address + ", " + city + ", UT " + zip_code, 66)
        weight = pad_spaces(str(self.weight) + " kg", 6, True)
        deadline = pad_spaces(self.deadline, 8)
        status = self.status
        print(pid + " | " + location_str + " | " + weight + " | " + deadline + " | " + status)


# Utility method to add spaces before or after a string. Runs in O(1)
def pad_spaces(string, total_length, before=False):
    spaces = " " * (total_length - len(string))
    if before:
        padded = spaces + string
    else:
        padded = string + spaces
    return padded


# Prints attributes and status of all packages and trucks. O(n)
def print_status(packages, clock, trucks):
    print(" ")
    print("Current time: " + str(clock.now()))
    print("Package ID | " + pad_spaces("Delivery Location", 66) + " | Weight | Deadline | Status")
    for package in packages:
        package.print_status()
    print(" ")
    mile_tenths = 0
    for truck in trucks:
        mile_tenths += truck.mile_tenths_driven
        print("Truck " + str(truck.truck_id) + " has driven " + str(truck.miles_driven()) + " miles")
    print("Total miles driven: " + str(mile_tenths / 10.0))


class Truck(object):
    # This class represents a delivery truck. Initializes in O(1)
    def __init__(self, truck_id, hub, clock, capacity):
        self.truck_id = truck_id
        self.hub = hub
        self.clock = clock
        self.capacity = capacity
        self.mile_tenths_driven = 0
        self.mile_tenths_to_destination = 0
        self.packages = []
        self.destination = None
        self.location = hub
        self.waiting = False

    # Loads a package onto the truck. The first package loaded determines the first destination. O(1)
    def add_package(self, package):
        if len(self.packages) < self.capacity:
            self.packages.append(package)
            package.status = "On Truck " + str(self.truck_id)
        if len(self.packages) == 1:
            self.set_destination()
            self.waiting = False

    # Updates the truck's mileage and distance to the current destination. Time complexity of the method
    # is normally O(1) but the arrive method can trigger delivery or a new batch of packages to be loaded,
    # both of which are more complex algorithms. See comments on those methods for a more in-depth discussion
    # of their time complexities.
    def drive(self):
        if self.waiting:
            self.hub.arrive(self)
        elif self.mile_tenths_to_destination > 0:
            self.mile_tenths_driven += 1
            self.mile_tenths_to_destination -= 1
            if self.mile_tenths_to_destination == 0:
                self.location = self.destination
                self.destination.arrive(self)

    # Delivers packages matching the address of the current location and replaces the list of packages
    # on the truck with the remaining packages after delivery is complete. This method always runs in O(n).
    def deliver(self):
        remaining_packages = []
        for package in self.packages:
            if package.delivery_location == self.location:
                if self.clock.now() <= package.deadline_time:
                    on_time = " (On time)"
                else:
                    on_time = " (Late)"
                package.status = "Delivered at " + str(self.clock.now()) + on_time
            else:
                remaining_packages.append(package)
        self.packages = remaining_packages
        self.set_destination()

    # Sets the location of the next destination and the number of miles to reach it. O(1)
    def set_destination(self):
        if len(self.packages) == 0:
            self.destination = self.hub
        else:
            self.destination = self.packages[0].delivery_location
        self.mile_tenths_to_destination = int(10 * self.location.distance_to(self.destination))

    # Commands a truck to wait at the hub when no deliverable packages are available. O(1)
    def wait_at_hub(self):
        self.waiting = True

    # Converts truck mileage into miles. The mileage on the trucks is tracked using integers representing
    # tenths of a mile driven because of the greater precision inherent to integer math over floating point
    # math. It is more accurate to make calculations with integers and convert to floating point only when
    # reporting the total. O(1)
    def miles_driven(self):
        return self.mile_tenths_driven / 10.0


# Utility method for converting a csv file into a table, represented by a list of lists where each inner
# list is a row of the csv file. Runs in O(n).
def read_csv(file_path):
    import csv
    table = []
    with open(file_path) as file:
        reader = csv.reader(file)
        for row in reader:
            table.append(row)
    return table


# Instantiates the Location objects by reading their attributes and the distance table from a csv file.
# Runs in O(n^2)
def setup_locations(packages, clock):
    raw_table = read_csv("locations.csv")
    distance_table = []
    locations = []
    for i in range(len(raw_table)):
        address = raw_table[i][0]
        city = raw_table[i][1]
        zip_code = raw_table[i][2]
        if i == 0:
            locations.append(Hub(i, address, city, zip_code, distance_table, packages, clock))
        else:
            locations.append(Location(i, address, city, zip_code, distance_table))
        distances = []
        j = 3
        while j < len(raw_table[i]) and raw_table[i][j] != "":
            distances.append(float(raw_table[i][j]))
            j += 1
        distance_table.append(distances)
    return locations


# Instantiates the Package objects by reading their attributes from a csv file, then adds the packages
# to a HashTable serving as the master list of Packages. Runs in O(n^2)
def setup_packages(packages, locations):
    raw_table = read_csv("packages.csv")
    # O(n) loop
    for i in range(len(raw_table)):
        package_id = int(raw_table[i][0])
        address = raw_table[i][1]
        city = raw_table[i][2]
        zip_code = raw_table[i][3]
        deadline = raw_table[i][4]
        weight = int(raw_table[i][5])
        status = raw_table[i][6]
        truck2_only = raw_table[i][7] == "Truck 2 Only"
        deliver_with = []
        j = 8
        while j < len(raw_table[i]) and raw_table[i][j] != "":
            deliver_with.append(int(raw_table[i][j]))
            j += 1
        # O(n) loop to assign the correct instantiated Location object to the package
        for location in locations:
            if location.address == address and location.city == city and location.zip_code == zip_code:
                package = Package(package_id, location, weight, deadline, status, truck2_only, deliver_with)
                packages.add(package_id, package)
                break


# Instantiates the Simulator object and all of its dependencies. Runs in O(n^2)
def setup_simulator(stop_at):
    # Per requirements, the day starts at 8 AM. A timedelta increment of 20 seconds is used because
    # the trucks travel 18 mph, which is 0.3 miles/minute, or 0.1 mile every 20 seconds, and all the
    # distances are rounded to the nearest tenth of a mile.
    clock = Clock(time(8, 0, 0), timedelta(0, 20))
    packages = HashTable()
    locations = setup_locations(packages, clock)
    hub = locations[0]
    setup_packages(packages, locations)
    trucks = []
    for i in range(1, 4):
        trucks.append(Truck(i, hub, clock, 16))
    return Simulator(hub, trucks, clock, locations, stop_at)


# Displays main menu and prompts for user selection. Runs in O(1), may lead to method call that runs in O(n^3).
def display_menu():
    print("Welcome to the WGUPS Package Delivery Simulator!")
    print("Please select from the following options:")
    print("1: Run until end of day")
    print("2: Run until a specific time")
    print("3: Exit")
    return parse_menu_selection(input("Your selection: "))


# Executes main menu selection of the user or prompts to try again. O(1) base method but may call a method
# that runs in O(n^3).
def parse_menu_selection(user_input):
    run_again = True
    if user_input == "1":
        setup_simulator(time(17, 0, 0)).run()
    elif user_input == "2":
        select_time()
    elif user_input == "3":
        run_again = False
    else:
        print("Sorry, that is an invalid selection.")
    return run_again


# Prompts user for time to end simulation. Runs in O(1) but calls a method that runs O(n^3).
def select_time():
    print("What time should the simulation stop?")
    print("Use the format HH:MM (HH 8-23, MM 0-59)")
    parse_time_selection(input("Time: "))


# Runs simulation until time specified by the user or prompts to try again. Method called runs in O(n^3).
def parse_time_selection(user_input):
    try:
        colon_pos = user_input.find(":")
        hour = int(user_input[:colon_pos])
        minute = int(user_input[colon_pos + 1:])
        if hour < 8 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        setup_simulator(time(hour, minute, 0)).run()
    except ValueError:
        print("Sorry, that selection is invalid.")
        select_time()


# Displays main menu and returns True if user does not select option to exit. O(1) base but may call O(n^3) method
def program_running():
    run_again = display_menu()
    print(" ")
    return run_again


# Program launcher, time complexity O(n^3) matching the largest time complexity of the whole program.
if __name__ == "__main__":
    while program_running():
        pass
