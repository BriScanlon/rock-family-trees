import axios from 'axios'

const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '/api' })

export const apiUrl = (path) => `${client.defaults.baseURL}${path}`

export const searchArtists = (q) => client.get('/search', { params: { q } }).then((r) => r.data)
export const listSamples = () => client.get('/samples').then((r) => r.data)
export const startGeneration = (body) => client.post('/generate', body).then((r) => r.data)
export const getStatus = (jobId) => client.get(`/status/${jobId}`).then((r) => r.data)

export const errorMessage = (err) =>
  err?.response?.data?.detail
    ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : 'Invalid request')
    : err?.message || 'Something went wrong'
