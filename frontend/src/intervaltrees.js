// Node class representing an interval and the max value in its subtree
class IntervalNode {
    constructor(interval, value) {
        let [low, high] = interval;
        if (high < low) [high,low] = interval;
        this.interval = [low,high]
        this.low = low;
        this.high = high;
        this.max = high;
        this.left = null;
        this.right = null;
        this.value = value;
    }
}

// Interval Tree class
class IntervalTree {
    constructor() {
        this.root = null;
    }

    // Insert a new interval
    insert(interval, value) {
        this.root = this._insert(this.root, interval, value);
    }

    _insert(node, interval, value) {
        if (node === null) {
            return new IntervalNode(interval, value);
        }

        if (interval[0] < node.interval[0]) {
            node.left = this._insert(node.left, interval, value);
        } else {
            node.right = this._insert(node.right, interval, value);
        }

        // Update the max value
        if (node.max < interval[1]) {
            node.max = interval[1];
        }

        return node;
    }

    // Search for all intervals overlapping with given interval
    search(interval, filter) {
        let orderedInterval = [...interval];
        if (interval[1] < interval[0]) orderedInterval = [interval[1], interval[0]];
        const result = [];
        this._search(this.root, orderedInterval, filter instanceof Function ? filter : ()=>1, result);
        return result;
    }

    searchValue(interval, filter) {
        let orderedInterval = [...interval];
        if (interval[1] < interval[0]) orderedInterval = [interval[1], interval[0]];
        const result = this.search(orderedInterval, filter);
        return result.map(r=>r.value);
    }

    _search(node, interval, filter, result) {
        if (node === null) return;

        // Check if current node overlaps
        if (this._doOverlap(node.interval, interval) && filter(node)) {
            result.push(node);
        }

        // If left child's max is >= interval[0] (low), then search left
        if (node.left !== null && node.left.max >= interval[0]) {
            this._search(node.left, interval, filter, result);
        }

        // Always check right if needed
        this._search(node.right, interval, filter, result);
    }

    _doOverlap(i1, i2) {
        return i1[0] <= i2[1] && i2[0] <= i1[1];
    }
}

export { IntervalTree }