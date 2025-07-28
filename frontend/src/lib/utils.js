import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

export function convertErrors(error, setError, keys = []) {
    /*
    *   Convert errors from app store context to react-hook-form context
    */
    if (error && error.length) {
        let match = false;
        error.forEach((err) => {
            keys.forEach((key) => {
                if (err.startsWith(`${key}: `) && !match) {
                    setError(key, { type: "server", message: err.replace(`${key}: `, "") });
                    match = true;
                }
            })
            if (!match) {
                setError("general", { type: "server", message: err });
            }
        });
    }
}

export function truncateGUID(guid) {
    const cleanGuid = guid.replace(/-/g, '');
    return `${cleanGuid.substring(0, 4)}...${cleanGuid.substring(cleanGuid.length - 4)}`;
}

export function isGUID(guid) {
    return guid.match(/[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}/g)
}

export function randgrad(idx) {
    const GRADIENT = ["bg-gradient-to-br from-lime-300 to-emerald-300", "bg-gradient-to-br from-emerald-300 to-cyan-300", "bg-gradient-to-br from-rose-300 to-neutral-300", "bg-gradient-to-br from-fuchsia-300 to-sky-300", "bg-gradient-to-br from-pink-300 to-orange-300", "bg-gradient-to-br from-fuchsia-300 to-indigo-300", "bg-gradient-to-br from-violet-300 to-red-300", "bg-gradient-to-br from-fuchsia-300 to-lime-300", "bg-gradient-to-br from-zinc-300 to-yellow-300", "bg-gradient-to-br from-blue-500 to-purple-600"]
    return GRADIENT[idx % GRADIENT.length]
}


export const transition = (delay = 0, reduceMotion = false) => {
    if (!reduceMotion) {
        return (
            { initial: { y: -30, opacity: 0 }, animate: { y: 0, opacity: 1 }, exit: { opacity: 0, transition: { duration: .2 } }, transition: { type: "spring", stiffness: 300, damping: 50, delay: delay * 0.07 } }
        )
    }
    return {
        initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0, transition: { duration: .2 } }, transition: { type: "spring", stiffness: 300, damping: 50 }
    }
}

export function isNewChatLocation(location) {
    return location.pathname.split("/").includes("assistant")
}