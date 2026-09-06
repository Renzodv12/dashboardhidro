/* Prototipo SOLO simulado: potenciómetros y LEDs. No conectar bombas químicas. */
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <math.h>
#if __has_include("hidroponia_config.h")
#include "hidroponia_config.h"
#else
#include "hidroponia_config.example.h"
#endif

WiFiClient wifi;
PubSubClient mqtt(wifi);
const int inputs[] = {34,35,32,33,36,39};
const char* variables[] = {"ph","tds","temperatura_agua","temperatura_ambiente","humedad","nivel"};
const char* units[] = {"pH","ppm","°C","°C","%","%"};
const float minima[] = {4,400,15,15,20,0};
const float maxima[] = {9,1500,32,38,95,100};
const int PLUS_LED=18, MINUS_LED=19;
float output=0, phCorrection=0;
unsigned long expiresAt=0, lastPublish=0, lastStep=0, lastConnect=0, continuousAt=0;
bool latched=false;
String previousCommand;

void leds() { digitalWrite(PLUS_LED,output>0); digitalWrite(MINUS_LED,output<0); }
void stopActuation() { output=0; leds(); }

String timestampUTC() {
  time_t now=time(nullptr); struct tm tm; gmtime_r(&now,&tm);
  char result[32]; strftime(result,sizeof(result),"%Y-%m-%dT%H:%M:%SZ",&tm);
  return String(result);
}

void callback(char* topic, byte* bytes, unsigned int length) {
  if(length>1024) return;
  JsonDocument doc;
  if(deserializeJson(doc,bytes,length)) return;
  if(String(doc["device_id"] | "")!=DEVICE_ID) return;
  String command=doc["command_id"] | "";
  if(command.length()==0 || command==previousCommand) return;
  const char* stamp=doc["timestamp"] | "";
  struct tm tm={};
  if(!strptime(stamp,"%Y-%m-%dT%H:%M:%S",&tm)) return;
  double age=difftime(time(nullptr),mktime(&tm));
  if(age<0 || age>=3) return;
  if(!doc["output"].is<float>() && !doc["output"].is<int>()) return;
  if(!doc["ttl"].is<float>() && !doc["ttl"].is<int>()) return;
  float requested=doc["output"], ttl=doc["ttl"];
  if(!isfinite(requested)||!isfinite(ttl)||fabs(requested)>40||ttl<0||ttl>3) return;
  previousCommand=command;
  if(requested==0) { stopActuation(); latched=false; continuousAt=0; return; }
  if(latched) return;
  if(output==0) continuousAt=millis();
  output=requested;
  expiresAt=millis()+(unsigned long)(fmax(0,ttl-age)*1000);
  leds();
}

void setup() {
  Serial.begin(115200);
  pinMode(PLUS_LED,OUTPUT); pinMode(MINUS_LED,OUTPUT); stopActuation();
  analogReadResolution(12);
  WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  setenv("TZ","UTC0",1); tzset(); configTime(0,0,"pool.ntp.org");
  mqtt.setServer(MQTT_HOST,MQTT_PORT); mqtt.setCallback(callback);
  mqtt.setBufferSize(1024); mqtt.setSocketTimeout(1); mqtt.setKeepAlive(10);
  lastStep=millis();
}

void loop() {
  unsigned long now=millis();
  if(!mqtt.connected() || (int32_t)(now-expiresAt)>=0) stopActuation();
  if(output!=0 && now-continuousAt>=45000) {stopActuation();latched=true;}
  float level=analogRead(inputs[5])*100.0/4095.0;
  if(level<25) stopActuation();
  float dt=fmin((now-lastStep)/1000.0,.2); lastStep=now;
  phCorrection+=output*.0025*dt;
  if(WiFi.status()!=WL_CONNECTED) {stopActuation();delay(10);return;}
  if(!mqtt.connected()) {
    stopActuation();
    if(now-lastConnect>=2000) {
      lastConnect=now;
      if(mqtt.connect(DEVICE_ID,MQTT_USERNAME,MQTT_PASSWORD)) mqtt.subscribe("hidroponia/control/ph",0);
    }
    delay(10);return;
  }
  mqtt.loop();
  if(now-lastPublish>=1000 && time(nullptr)>1700000000) {
    lastPublish=now;
    for(int i=0;i<6;i++) {
      float value=minima[i]+analogRead(inputs[i])/4095.0*(maxima[i]-minima[i]);
      if(i==0) value=fmax(4,fmin(9,value+phCorrection));
      JsonDocument doc;
      doc["device_id"]=DEVICE_ID;doc["variable"]=variables[i];doc["value"]=value;
      doc["unit"]=units[i];doc["timestamp"]=timestampUTC();doc["source"]="wokwi";
      doc["message_id"]=String((uint32_t)time(nullptr))+"-"+String(now)+"-"+String(i);
      char payload[512];serializeJson(doc,payload,sizeof(payload));
      mqtt.publish((String("hidroponia/sensores/")+variables[i]).c_str(),payload,false);
    }
    JsonDocument state;state["output"]=output;
    char payload[80];serializeJson(state,payload,sizeof(payload));
    mqtt.publish((String("hidroponia/estado/")+DEVICE_ID).c_str(),payload,false);
    Serial.printf("Salida simulada: %+.1f%%; nivel %.1f%%\n",output,level);
  }
  delay(5);
}
