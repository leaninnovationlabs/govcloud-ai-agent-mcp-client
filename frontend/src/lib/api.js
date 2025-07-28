import { API_BASE, API_ENDPOINTS } from "./constants";


class API {
    static async grab(method, endpoint, body = {}, options = {}) {
        const { params, raw, ...rest } = options

        const url = API_BASE + endpoint + (!!params ? "?" + new URLSearchParams(params).toString() : "")

        const res = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            ...rest,
            ...(body ? {
                body: JSON.stringify({
                    ...body
                })
            } : {})
        });
        if (raw) {
            return res
        }

        if (res.status === 401 && ![API_ENDPOINTS.STATUS, API_ENDPOINTS.LOGIN].includes(endpoint)) {
            // Trigger Logout 
            console.warn("Logging out ...")
            location.reload()
            
        }
        const json = await res.json()
        if (!res.ok) {
            throw json.errors
        }
        return json

    }
    static async get(endpoint, options = {}) {
        return this.grab("get", endpoint, null, options)
    }

    static async post(endpoint, body = {}, options = {}) {
        return this.grab("post", endpoint, body, options)
    }

    static async put(endpoint, body = {}, options = {}) {
        return this.grab("put", endpoint, body, options)
    }

    static async delete(endpoint, options = {}) {
        return this.grab("delete", endpoint, null, options)
    }

}

export default API