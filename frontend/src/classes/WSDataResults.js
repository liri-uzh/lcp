/**
 * Class representing WebSocket data results
 * Encapsulates query results and related metadata
 */
class WSDataResults {
  /**
   * Create a WSDataResults instance
   * @param {Object} data - Initial data to populate the instance
   */
  constructor(data = {}) {
    // Initialize properties with default values
    this.result = data.result || {};
    this.percentage_done = data.percentage_done || 0;
    this.percentage_words_done = data.percentage_words_done || 0;
    this.total_results_so_far = data.total_results_so_far || 0;
    this.projected_results = data.projected_results || 0;
    this.batches_done = data.batches_done || 0;
    this.status = data.status || null;
    this.more_data_available = data.more_data_available || false;
    this.request_id = data.request_id || null;
    this.n_results = data.n_results || 0;
  }

  /**
   * Update properties from a data object
   * @param {Object} data - Data to update from
   */
  updateFromData(data) {
    if (data) {
      this.result = data.result || this.result;
      this.percentage_done = data.percentage_done || this.percentage_done;
      this.percentage_words_done = data.percentage_words_done || this.percentage_words_done;
      this.total_results_so_far = data.total_results_so_far || this.total_results_so_far;
      this.projected_results = data.projected_results || this.projected_results;
      this.batches_done = data.batches_done || this.batches_done;
      this.status = data.status || this.status;
      this.more_data_available = data.more_data_available || this.more_data_available;
      this.request_id = data.request_id || this.request_id;
      this.n_results = data.n_results || this.n_results;
    }
    return this;
  }

  /**
   * Get the percentage done
   * @returns {number} Percentage done (0-100)
   */
  getPercentageDone() {
    return this.percentage_done || 0;
  }

  /**
   * Get the total percentage done based on results
   * @returns {number} Total percentage done (0-100)
   */
  getTotalPercentageDone() {
    if (this.total_results_so_far && this.projected_results) {
      return (this.total_results_so_far / this.projected_results) * 100;
    }
    return 0;
  }

  /**
   * Check if the query is finished
   * @returns {boolean} True if finished
   */
  isFinished() {
    return ["finished"].includes(this.status);
  }

  /**
   * Check if the query is satisfied
   * @returns {boolean} True if satisfied
   */
  isSatisfied() {
    return ["satisfied", "overtime"].includes(this.status);
  }

  /**
   * Check if more data is available
   * @returns {boolean} True if more data is available
   */
  hasMoreData() {
    return this.more_data_available;
  }

  /**
   * Get result sets from the first result
   * @returns {Array} Array of result sets or empty array
   */
  getResultSets() {
    return this.result['0']?.result_sets || [];
  }

  /**
   * Get result data for a specific index
   * @param {number} index - Result index
   * @returns {Array} Result data or empty array
   */
  getResultData(index) {
    return this.result[index + 1] || [];
  }

  /**
   * Clear all results data
   */
  clear() {
    this.result = {};
    this.percentage_done = 0;
    this.percentage_words_done = 0;
    this.total_results_so_far = 0;
    this.projected_results = 0;
    this.batches_done = 0;
    this.status = null;
    this.more_data_available = false;
    this.request_id = null;
    this.n_results = 0;
  }

  /**
   * Check if results are empty
   * @returns {boolean} True if no results
   */
  isEmpty() {
    return !this.result || Object.keys(this.result).length === 0;
  }

  /**
   * Convert to plain object (for JSON serialization, etc.)
   * @returns {Object} Plain object representation
   */
  toObject() {
    return {
      result: this.result,
      percentage_done: this.percentage_done,
      percentage_words_done: this.percentage_words_done,
      total_results_so_far: this.total_results_so_far,
      projected_results: this.projected_results,
      batches_done: this.batches_done,
      status: this.status,
      more_data_available: this.more_data_available,
      request_id: this.request_id
    };
  }

  /**
   * Create from WebSocket message data
   * @param {Object} message - WebSocket message data
   * @returns {WSDataResults} New instance
   */
  static fromWebSocketMessage(message) {
    return new WSDataResults(message.data || message);
  }
}

class DataLine {
  constructor(line, n) {
    const copyLine = [...line];
    this.id = n;
    this.sentenceId = copyLine.shift();
    this.char_range = copyLine.pop();
    this.hits = copyLine.pop();
  }
}

export { DataLine };
export default WSDataResults;