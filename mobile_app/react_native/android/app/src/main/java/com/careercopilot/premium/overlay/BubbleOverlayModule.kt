package com.careercopilot.premium.overlay

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.WritableNativeMap


class BubbleOverlayModule(private val reactContext: ReactApplicationContext) : ReactContextBaseJavaModule(reactContext) {
    private val prefsName = "career_copilot_mobile"
    private val baseUrlKey = "preferred_base_url"
    private val sessionIdKey = "preferred_session_id"

    override fun getName(): String = "BubbleOverlayModule"

    @ReactMethod
    fun getOverlayStatus(promise: Promise) {
        val payload = WritableNativeMap()
        payload.putBoolean("available", true)
        payload.putBoolean("canDrawOverlays", Settings.canDrawOverlays(reactContext))
        payload.putBoolean("serviceRunning", BubbleOverlayService.running)
        promise.resolve(payload)
    }

    @ReactMethod
    fun openOverlaySettings(promise: Promise) {
        val intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:${reactContext.packageName}"),
        ).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        reactContext.startActivity(intent)
        promise.resolve("Opened Android overlay settings.")
    }

    @ReactMethod
    fun startBubbleOverlay(baseUrl: String, sessionId: String, promise: Promise) {
        if (!Settings.canDrawOverlays(reactContext)) {
            promise.resolve("Overlay permission is required before starting the bubble.")
            return
        }

        val intent = Intent(reactContext, BubbleOverlayService::class.java).apply {
            putExtra(BubbleOverlayService.EXTRA_BASE_URL, baseUrl)
            putExtra(BubbleOverlayService.EXTRA_SESSION_ID, sessionId)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            reactContext.startForegroundService(intent)
        } else {
            reactContext.startService(intent)
        }
        promise.resolve("Started Android bubble overlay service.")
    }

    @ReactMethod
    fun stopBubbleOverlay(promise: Promise) {
        reactContext.stopService(Intent(reactContext, BubbleOverlayService::class.java))
        promise.resolve("Stopped Android bubble overlay service.")
    }

    @ReactMethod
    fun savePreferredConnection(baseUrl: String, sessionId: String, promise: Promise) {
        val prefs = reactContext.getSharedPreferences(prefsName, 0)
        prefs.edit()
            .putString(baseUrlKey, baseUrl)
            .putString(sessionIdKey, sessionId)
            .apply()
        promise.resolve("Saved preferred desktop connection.")
    }

    @ReactMethod
    fun getPreferredConnection(promise: Promise) {
        val prefs = reactContext.getSharedPreferences(prefsName, 0)
        val payload = WritableNativeMap()
        payload.putString("baseUrl", prefs.getString(baseUrlKey, "") ?: "")
        payload.putString("sessionId", prefs.getString(sessionIdKey, "") ?: "")
        promise.resolve(payload)
    }

    @ReactMethod
    fun clearPreferredConnection(promise: Promise) {
        val prefs = reactContext.getSharedPreferences(prefsName, 0)
        prefs.edit().remove(baseUrlKey).remove(sessionIdKey).apply()
        promise.resolve("Cleared preferred desktop connection.")
    }
}