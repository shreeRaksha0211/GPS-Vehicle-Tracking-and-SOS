package com.example.safetrack
import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.widget.*
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
class MainActivity:Activity(){
 lateinit var vid:EditText; lateinit var key:EditText; lateinit var status:TextView
 override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState)
  val box=LinearLayout(this).apply{orientation=1;setPadding(28,40,28,20)}
  box.addView(TextView(this).apply{text="SafeTrack — GPS sharing";textSize=24f})
  box.addView(TextView(this).apply{text="Enter the vehicle ID and one-time device secret from the owner's web account."})
  vid=EditText(this).apply{hint="Vehicle ID";inputType=InputType.TYPE_CLASS_NUMBER}
  key=EditText(this).apply{hint="Device secret";inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD}
  status=TextView(this).apply{text="Tracking is off"}
  box.addView(vid);box.addView(key)
  box.addView(Button(this).apply{text="Start visible tracking";setOnClickListener{startTracking()}})
  box.addView(Button(this).apply{text="Stop tracking";setOnClickListener{stopService(Intent(this@MainActivity,TrackingService::class.java));status.text="Stopped"}})
  box.addView(status);setContentView(box)
 }
 private fun startTracking(){
  val id=vid.text.toString().toIntOrNull();val secret=key.text.toString()
  if(id==null||secret.isBlank()){status.text="Enter vehicle ID and secret";return}
  val p=mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION)
  if(Build.VERSION.SDK_INT>=33)p.add(Manifest.permission.POST_NOTIFICATIONS)
  val missing=p.filter{ContextCompat.checkSelfPermission(this,it)!=PackageManager.PERMISSION_GRANTED}
  if(missing.isNotEmpty()){ActivityCompat.requestPermissions(this,missing.toTypedArray(),5);status.text="Grant permissions, then tap Start again";return}
  ContextCompat.startForegroundService(this,Intent(this,TrackingService::class.java).putExtra("id",id).putExtra("secret",secret));status.text="Tracking started; persistent notification is visible."
 }
}
