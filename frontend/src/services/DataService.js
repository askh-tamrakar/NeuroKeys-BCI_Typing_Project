/**
 * DataService
 * Handles persistence of recorded sessions to the backend.
 */
export const DataService = {
    /**
     * Saves a recorded session to the server.
     * @param {string} filename - The formatted filename.
     * @param {Object} payload - The session data.
     * @returns {Promise<Object>} The server response.
     */
    async saveSession(filename, payload) {
        try {
            const response = await fetch('/api/record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, payload })
            });

            if (!response.ok) {
                let errorMessage = 'Failed to save session';
                try {
                    const err = await response.json();
                    errorMessage = err.error || errorMessage;
                } catch (e) {
                    // If not JSON, use status text
                    errorMessage = `${response.status} ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('[DataService] Error saving session:', error);
            throw error;
        }
    }
};
