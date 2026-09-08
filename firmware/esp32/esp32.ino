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
float output=0;
float simulatedOffsets[6]={0,0,0,0,0,0};
// Único adaptador actual: potenciómetros y LEDs. No hay driver de bombas.
float readSimulatedSensor(int index) {
  float value=minima[index]+analogRead(inputs[index])/4095.0*(maxima[index]-minima[index]);
  return fmax(minima[index],fmin(maxima[index],value+simulatedOffsets[index]));
}
String topic(const char* suffix) { return String(MQTT_TOPIC_PREFIX)+suffix; }
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
  bool disturbance=String(topic)==::topic("/simulation/disturbance");
  if(!disturbance && String(topic)!=::topic("/control/ph")) return;
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
  if(disturbance) {
    if(!doc["delta"].is<float>() && !doc["delta"].is<int>()) return;
    float delta=doc["delta"];
    if(!isfinite(delta)||fabs(delta)>1000) return;
    for(int i=0;i<6;i++) if(String(doc["variable"] | "")==variables[i]) {
      float before=readSimulatedSensor(i);
      float after=fmax(minima[i],fmin(maxima[i],before+delta));
      simulatedOffsets[i]+=after-before;
      previousCommand=command;
      return;
    }
    return;
  }
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
  float level=readSimulatedSensor(5);
  if(level<25) stopActuation();
  float dt=fmin((now-lastStep)/1000.0,.2); lastStep=now;
  simulatedOffsets[0]+=output*.0025*dt;
  if(WiFi.status()!=WL_CONNECTED) {stopActuation();delay(10);return;}
  if(!mqtt.connected()) {
    stopActuation();
    if(now-lastConnect>=2000) {
      lastConnect=now;
      if(mqtt.connect(DEVICE_ID,MQTT_USERNAME,MQTT_PASSWORD)) {
        mqtt.subscribe(topic("/control/ph").c_str(),0);
        mqtt.subscribe(topic("/simulation/disturbance").c_str(),0);
        Serial.println("MQTT conectado: "+String(MQTT_TOPIC_PREFIX));
      } else Serial.printf("MQTT error: %d\n",mqtt.state());
    }
    delay(10);return;
  }
  mqtt.loop();
  if(now-lastPublish>=1000 && time(nullptr)>1700000000) {
    lastPublish=now;
    for(int i=0;i<6;i++) {
      float value=readSimulatedSensor(i);
      JsonDocument doc;
      doc["device_id"]=DEVICE_ID;doc["variable"]=variables[i];doc["value"]=value;
      doc["unit"]=units[i];doc["timestamp"]=timestampUTC();doc["source"]="wokwi";
      doc["message_id"]=String((uint32_t)time(nullptr))+"-"+String(now)+"-"+String(i);
      char payload[512];serializeJson(doc,payload,sizeof(payload));
      mqtt.publish((topic("/sensores/")+variables[i]).c_str(),payload,false);
    }
    JsonDocument state;state["output"]=output;
    char payload[80];serializeJson(state,payload,sizeof(payload));
    mqtt.publish((topic("/estado/")+DEVICE_ID).c_str(),payload,false);
    Serial.printf("Salida simulada: %+.1f%%; nivel %.1f%%\n",output,level);
  }
  delay(5);
}
