package com.example.safetrack
import android.app.*
import android.content.Intent
import android.os.*
import com.google.android.gms.location.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
class TrackingService:Service(){
 lateinit var fused:FusedLocationProviderClient; var cb:LocationCallback?=null; var id=0;var secret=""
 val client=OkHttpClient()
 override fun onCreate(){super.onCreate();fused=LocationServices.getFusedLocationProviderClient(this);if(Build.VERSION.SDK_INT>=26)getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("gps","GPS tracking",NotificationManager.IMPORTANCE_LOW))}
 override fun onStartCommand(i:Intent?,flags:Int,startId:Int):Int{
  id=i?.getIntExtra("id",0)?:0;secret=i?.getStringExtra("secret")?:"";if(id<=0||secret.isBlank()){stopSelf();return START_NOT_STICKY}
  val n=Notification.Builder(this,"gps").setContentTitle("SafeTrack location sharing active").setContentText("GPS is being shared for your registered vehicle. Stop in the app.").setSmallIcon(android.R.drawable.ic_menu_mylocation).setOngoing(true).build()
  startForeground(12,n)
  val req=LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY,5000).setMinUpdateIntervalMillis(3000).build()
  cb=object:LocationCallback(){override fun onLocationResult(r:LocationResult){val l=r.lastLocation?:return;send(l.latitude,l.longitude,l.accuracy.toDouble(),l.speed.toDouble(),l.bearing.toDouble())}}
  try{fused.requestLocationUpdates(req,cb!!,mainLooper)}catch(e:SecurityException){stopSelf()}
  return START_STICKY
 }
 fun send(lat:Double,lon:Double,acc:Double,speed:Double,heading:Double){
  val j=JSONObject().put("vehicle_id",id).put("device_secret",secret).put("lat",lat).put("lon",lon).put("accuracy",acc).put("speed",speed).put("heading",heading)
  val body=j.toString().toRequestBody("application/json".toMediaType())
  val req=Request.Builder().url(Config.BASE_URL+"api/location").post(body).build()
  client.newCall(req).enqueue(object:Callback{override fun onFailure(call:Call,e:IOException){};override fun onResponse(call:Call,response:Response){response.close()}})
 }
 override fun onDestroy(){cb?.let{fused.removeLocationUpdates(it)};super.onDestroy()}
 override fun onBind(i:Intent?):IBinder?=null
}
