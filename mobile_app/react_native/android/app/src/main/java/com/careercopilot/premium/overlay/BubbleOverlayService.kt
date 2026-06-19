package com.careercopilot.premium.overlay

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.DisplayMetrics
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.careercopilot.premium.MainActivity
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread
import kotlin.math.abs

class BubbleOverlayService : Service() {
    private lateinit var windowManager: WindowManager
    private val handler = Handler(Looper.getMainLooper())
    private var bubbleView: TextView? = null
    private var panelView: LinearLayout? = null
    private var headlineView: TextView? = null
    private var bodyView: TextView? = null
    private var statusView: TextView? = null
    private var bubbleParams: WindowManager.LayoutParams? = null
    private var panelParams: WindowManager.LayoutParams? = null
    private var baseUrl: String = ""
    private var sessionId: String = ""
    private var lastHeadline: String = ""
    private var lastBody: String = ""
    private var lastStatus: String = ""
    private var dragStartX = 0
    private var dragStartY = 0
    private var touchStartX = 0f
    private var touchStartY = 0f

    private val refreshRunnable = object : Runnable {
        override fun run() {
            refreshOverlay()
            handler.postDelayed(this, 4000)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        running = true
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        baseUrl = intent?.getStringExtra(EXTRA_BASE_URL).orEmpty()
        sessionId = intent?.getStringExtra(EXTRA_SESSION_ID).orEmpty()

        if (baseUrl.isBlank() || sessionId.isBlank() || !Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(NOTIFICATION_ID, buildNotification())
        if (bubbleView == null) {
            attachOverlayViews()
        }
        handler.removeCallbacks(refreshRunnable)
        handler.post(refreshRunnable)
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(refreshRunnable)
        bubbleView?.let(windowManager::removeView)
        panelView?.let(windowManager::removeView)
        bubbleView = null
        panelView = null
        running = false
        super.onDestroy()
    }

    private fun attachOverlayViews() {
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        windowManager.defaultDisplay.getMetrics(metrics)
        val panelWidth = (metrics.widthPixels * 0.92f).toInt().coerceAtMost(metrics.widthPixels - 48)

        bubbleView = TextView(this).apply {
            text = "CC"
            textSize = 16f
            minWidth = dp(56)
            minHeight = dp(56)
            gravity = Gravity.CENTER
            setPadding(dp(12), dp(12), dp(12), dp(12))
            setBackgroundColor(0xEE141F27.toInt())
            setTextColor(0xFFF3F7FA.toInt())
            setOnClickListener { togglePanel() }
            setOnTouchListener(::handleBubbleTouch)
        }
        panelView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(18))
            setBackgroundColor(0xEEF0EADF.toInt())
            visibility = View.GONE
        }
        headlineView = TextView(this).apply {
            textSize = 17f
            setTextColor(0xFF132129.toInt())
            maxLines = 3
        }
        bodyView = TextView(this).apply {
            textSize = 14f
            setTextColor(0xFF20333D.toInt())
            maxLines = 8
        }
        statusView = TextView(this).apply {
            textSize = 12f
            setTextColor(0xFF4F5D65.toInt())
            maxLines = 2
        }

        val actionRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(buildActionButton("Listen", "listen"))
            addView(buildActionButton("Toggle", "toggle"))
            addView(buildActionButton("Status", "status"))
        }

        panelView?.apply {
            addView(headlineView)
            addView(bodyView)
            addView(statusView)
            addView(actionRow)
        }

        bubbleParams = createLayoutParams(dp(56), dp(56), dp(24), dp(140))
        panelParams = createLayoutParams(panelWidth, WindowManager.LayoutParams.WRAP_CONTENT, dp(24), dp(220))

        windowManager.addView(bubbleView, bubbleParams)
        windowManager.addView(panelView, panelParams)
    }

    private fun handleBubbleTouch(view: View, event: MotionEvent): Boolean {
        val params = bubbleParams ?: return false
        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                dragStartX = params.x
                dragStartY = params.y
                touchStartX = event.rawX
                touchStartY = event.rawY
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                params.x = dragStartX + (event.rawX - touchStartX).toInt()
                params.y = dragStartY + (event.rawY - touchStartY).toInt()
                panelParams?.let { panel ->
                    panel.x = params.x
                    panel.y = params.y + dp(72)
                    windowManager.updateViewLayout(panelView, panel)
                }
                windowManager.updateViewLayout(bubbleView, params)
                return true
            }
            MotionEvent.ACTION_UP -> {
                val moved = abs(event.rawX - touchStartX) > dp(8) || abs(event.rawY - touchStartY) > dp(8)
                if (!moved) {
                    view.performClick()
                }
                return true
            }
        }
        return false
    }

    private fun buildActionButton(label: String, actionId: String): Button {
        return Button(this).apply {
            text = label
            isAllCaps = false
            setOnClickListener { sendAction(actionId) }
        }
    }

    private fun createLayoutParams(width: Int, height: Int, x: Int, y: Int): WindowManager.LayoutParams {
        val overlayType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }
        return WindowManager.LayoutParams(
            width,
            height,
            overlayType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            this.x = x
            this.y = y
        }
    }

    private fun togglePanel() {
        panelView?.visibility = if (panelView?.visibility == View.VISIBLE) View.GONE else View.VISIBLE
    }

    private fun refreshOverlay() {
        val targetUrl = "$baseUrl/session/$sessionId"
        thread(start = true) {
            try {
                val connection = URL(targetUrl).openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 8000
                val body = connection.inputStream.bufferedReader().use { it.readText() }
                val envelope = JSONObject(body)
                val overlay = envelope.getJSONObject("overlay")
                val snapshot = envelope.getJSONObject("snapshot")
                val headline = overlay.optString("headline", "Career Copilot")
                val bodyText = overlay.optString("body", "Waiting for live session state.")
                val statusText = "${overlay.optString("status", "idle")} | ${snapshot.optString("worker_status", "unknown")}"
                handler.post {
                    if (headline != lastHeadline) {
                        headlineView?.text = headline
                        lastHeadline = headline
                    }
                    if (bodyText != lastBody) {
                        bodyView?.text = bodyText
                        lastBody = bodyText
                    }
                    if (statusText != lastStatus) {
                        statusView?.text = statusText
                        lastStatus = statusText
                    }
                }
            } catch (error: Exception) {
                handler.post {
                    val message = error.message ?: "Bridge unavailable"
                    if (message != lastStatus) {
                        statusView?.text = message
                        lastStatus = message
                    }
                }
            }
        }
    }

    private fun sendAction(actionId: String) {
        val targetUrl = "$baseUrl/session/$sessionId/actions/$actionId"
        val readTimeoutMs = if (actionId == "listen") 90000 else 15000
        handler.post {
            if (actionId == "listen") {
                headlineView?.text = "Listening for the interviewer"
                bodyView?.text = "Desktop is capturing call audio now. Keep PC and phone on the same Wi-Fi."
                statusView?.text = "listen | running on desktop PC mic..."
            } else {
                statusView?.text = "Sending $actionId to desktop..."
            }
        }
        thread(start = true) {
            try {
                val connection = URL(targetUrl).openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.connectTimeout = 8000
                connection.readTimeout = readTimeoutMs
                connection.outputStream.use { }
                val body = connection.inputStream.bufferedReader().use { it.readText() }
                handler.post {
                    statusView?.text = if (actionId == "listen") {
                        "listen | desktop capture finished"
                    } else {
                        "Queued $actionId on desktop"
                    }
                    refreshOverlay()
                }
            } catch (_: Exception) {
                handler.post {
                    statusView?.text = "Could not reach desktop for $actionId"
                    if (actionId == "listen") {
                        bodyView?.text =
                            "Listen uses your PC microphone (not the phone). Check Wi-Fi, desktop app, and mic permissions."
                    }
                }
            }
        }
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).toInt()
    }

    private fun buildNotification(): Notification {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notificationManager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Career Copilot Bubble", NotificationManager.IMPORTANCE_LOW),
            )
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("Career Copilot Bubble")
                .setContentText("Overlay assistance is running.")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pendingIntent)
                .build()
        } else {
            Notification.Builder(this)
                .setContentTitle("Career Copilot Bubble")
                .setContentText("Overlay assistance is running.")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pendingIntent)
                .build()
        }
    }

    companion object {
        private const val CHANNEL_ID = "career_copilot_bubble"
        private const val NOTIFICATION_ID = 4107
        const val EXTRA_BASE_URL = "baseUrl"
        const val EXTRA_SESSION_ID = "sessionId"

        @Volatile
        var running: Boolean = false
    }
}
