/**
 * MuseumAPI — HTTP client for the AI Museum 3D backend.
 * Handles fetching museum metadata, galleries, exhibits, and search.
 */

class MuseumAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || '';
        this.metaCache = null;
        this.galleriesCache = null;
    }

    /**
     * Fetch museum metadata (galleries, themes, total exhibits).
     * @returns {Promise<Object>}
     */
    async getMeta() {
        if (this.metaCache) {
            return this.metaCache;
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/museum/meta`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.metaCache = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch museum meta:', error);
            return {
                name: 'AI Museum',
                description: 'Error loading museum metadata',
                galleries: [],
                total_exhibits: 0,
            };
        }
    }

    /**
     * Fetch gallery definitions with 3D positioning data.
     * @returns {Promise<Object>}
     */
    async getGalleries() {
        if (this.galleriesCache) {
            return this.galleriesCache;
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/museum/galleries`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.galleriesCache = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch galleries:', error);
            return { galleries: [] };
        }
    }

    /**
     * Fetch exhibits (corpus records) for a specific gallery.
     * @param {string} galleryId — Gallery ID (e.g., 'historian', 'sociologist')
     * @param {number} page — Page number (default 1)
     * @param {number} pageSize — Records per page (default 12)
     * @returns {Promise<Object>}
     */
    async getExhibits(galleryId, page = 1, pageSize = 12) {
        try {
            const url = `${this.baseUrl}/api/museum/exhibits/${galleryId}?page=${page}&pageSize=${pageSize}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            return data;
        } catch (error) {
            console.error(`Failed to fetch exhibits for ${galleryId}:`, error);
            return {
                gallery_id: galleryId,
                page,
                page_size: pageSize,
                total: 0,
                exhibits: [],
                insights: null,
            };
        }
    }

    /**
     * Search exhibits across galleries.
     * @param {string} query — Search term
     * @param {string|null} galleryId — Optional gallery filter
     * @param {number} pageSize — Max results (default 12)
     * @returns {Promise<Object>}
     */
    async search(query, galleryId = null, pageSize = 12) {
        if (!query || query.trim().length === 0) {
            return { query: '', results: [], total: 0 };
        }

        try {
            let url = `${this.baseUrl}/api/museum/search?query=${encodeURIComponent(query)}&pageSize=${pageSize}`;
            if (galleryId) {
                url += `&gallery=${encodeURIComponent(galleryId)}`;
            }
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Search failed:', error);
            return { query, results: [], total: 0 };
        }
    }
}
