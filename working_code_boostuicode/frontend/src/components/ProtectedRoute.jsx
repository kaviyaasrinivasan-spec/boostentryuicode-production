import { useEffect, useLayoutEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

export default function ProtectedRoute({ children }) {
  const isLoggedIn = localStorage.getItem("isLoggedIn");
  const location = useLocation();
  const navigate = useNavigate();

  // Check last activity on mount (handles tab close/reopen)
  useLayoutEffect(() => {
    if (isLoggedIn !== "true") return;
    try {
      const lastActivity = localStorage.getItem("lastActivity");
      console.log("[ProtectedRoute] mount check, lastActivity=", lastActivity);
      if (lastActivity) {
        const elapsed = Date.now() - Number(lastActivity);
        console.log("[ProtectedRoute] elapsed ms=", elapsed);
        if (elapsed > SESSION_TTL) {
          console.log("[ProtectedRoute] session expired on mount -> logging out");
          localStorage.removeItem("isLoggedIn");
          localStorage.removeItem("authToken");
          sessionStorage.clear();
          navigate("/login", { replace: true, state: { sessionExpired: true } });
          return;
        }
      } else {
        console.log("[ProtectedRoute] no lastActivity found on mount");
      }
    } catch (e) {
      console.warn("[ProtectedRoute] error reading lastActivity", e);
    }
  }, [isLoggedIn, navigate]);

  useEffect(() => {
    if (isLoggedIn !== "true") return;
    let inactivityTimer;
    let hiddenTimer;
    let sessionExpired = false;

    const logoutUser = () => {
      localStorage.removeItem("isLoggedIn");
      localStorage.removeItem("authToken");
      sessionStorage.clear();
      navigate("/login", { replace: true, state: { sessionExpired: true } });
    };

    const expireSession = () => {
      sessionExpired = true;
      console.log("⏳ Session expired — waiting for next interaction to log out...");
    };

    // Update last activity timestamp in localStorage
    const updateLastActivity = () => {
      localStorage.setItem("lastActivity", Date.now());
    };

    const handleUserInteraction = (event) => {
      if (sessionExpired) {
        logoutUser();
      } else {
        if (event.type === "click" || event.type === "keydown") {
          resetInactivityTimer();
          updateLastActivity();
        }
      }
    };

    const resetInactivityTimer = () => {
      clearTimeout(inactivityTimer);
      inactivityTimer = setTimeout(() => {
        expireSession();
      }, SESSION_TTL);
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        hiddenTimer = setTimeout(expireSession, SESSION_TTL);
      } else {
        clearTimeout(hiddenTimer);
      }
    };

    document.addEventListener("click", handleUserInteraction, true);
    document.addEventListener("keydown", handleUserInteraction);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Set initial last activity on mount
    updateLastActivity();
    resetInactivityTimer();

    return () => {
      clearTimeout(inactivityTimer);
      clearTimeout(hiddenTimer);
      document.removeEventListener("click", handleUserInteraction, true);
      document.removeEventListener("keydown", handleUserInteraction);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isLoggedIn, navigate]);

  if (isLoggedIn !== "true") {
    // Allow anonymous access to the upload page even when logged out
    try {
      const path = (location?.pathname || "").toLowerCase();
      if (path === "/upload" || path.startsWith("/upload/")) {
        return children;
      }
    } catch (e) {
      // ignore and fall through to redirect
    }

    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

// Production session TTL: 2 hours (milliseconds)
const SESSION_TTL = 2 * 60 * 60 * 1000;
