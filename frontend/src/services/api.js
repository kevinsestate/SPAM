import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

export const api = {
  async getStatus() {
    const response = await axios.get(`${API_BASE_URL}/api/status`)
    return response.data
  },

  async calibrate(parameters = {}) {
    const response = await axios.post(`${API_BASE_URL}/api/calibrate`, { parameters })
    return response.data
  },

  async startMeasurement() {
    const response = await axios.post(`${API_BASE_URL}/api/measurements/start`)
    return response.data
  },

  async createMeasurement(data) {
    const response = await axios.post(`${API_BASE_URL}/api/measurements`, data)
    return response.data
  },

  async getMeasurements(skip = 0, limit = 100) {
    const response = await axios.get(`${API_BASE_URL}/api/measurements`, {
      params: { skip, limit }
    })
    return response.data
  },

  async getMeasurement(id) {
    const response = await axios.get(`${API_BASE_URL}/api/measurements/${id}`)
    return response.data
  },

  async deleteMeasurement(id) {
    const response = await axios.delete(`${API_BASE_URL}/api/measurements/${id}`)
    return response.data
  },

  async exportData(format = 'json') {
    const response = await axios.get(`${API_BASE_URL}/api/export`, {
      params: { format }
    })
    return response
  }
}

