: '
Run as bash ./experiment.sh instead of sh experiment.sh since sh has less extensive syntax
else if statement will not execute properly
'

transmitProbability=0.05
numMobileDevice=20
numNetwork=5
networkDataRate="16_14_22_7_4"
nashEquilibrium="2_2_7_5_4"
listenProbability=0.33
delay=5
algorithmName="CollaborativeEWA"
numRun=100
eta=10
numTimeSlot=1200
maxTimeUnheardAcceptable=32
gamma=0
numSubTimeSlot=1
setting=4
saveMinimal=1
stableProbability=0.75
consecutiveStableSlot=10
rollingAvgWindow=10
echo "transmit with probability $transmitProbability"

rootDir="/home/anuja/Seagate/simulation_final/mobility_setting/$algorithmName"

mkdir $rootDir

runIndex=1
while [  $runIndex -lt $((numRun+1)) ]; do
    dir="$rootDir/run$runIndex/"
    mkdir $dir
    python3 wns_delayed_feedback.py -n $numMobileDevice -k $numNetwork -b $networkDataRate -t $numTimeSlot -st $numSubTimeSlot -a $algorithmName -s $setting -m $saveMinimal -e $eta -g $gamma -pt $transmitProbability -pl $listenProbability -d $delay -dir "$dir" -r $runIndex -ne $nashEquilibrium -max $maxTimeUnheardAcceptable
    runIndex=$((runIndex + 1 ))
done
if [ $setting -eq 4 ]
then
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 1 -ne "5,5,7,2,1" -u "1,2,3,4,5,6,7,8" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 1 -ne "5,5,7,2,1" -u "9,10" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 1 -ne "5,5,7,2,1" -u "11,12,13,14,15" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 1 -ne "5,5,7,2,1" -u "16,17,18,19,20" -b $networkDataRate

    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 2 -ne "6,2,9,2,1" -u "1,2,3,4,5,6,7,8" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 2 -ne "6,2,9,2,1" -u "9,10" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 2 -ne "6,2,9,2,1" -u "11,12,13,14,15" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 2 -ne "6,2,9,2,1" -u "16,17,18,19,20" -b $networkDataRate

    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 3 -ne "8,2,5,3,2" -u "1,2,3,4,5,6,7,8" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 3 -ne "8,2,5,3,2" -u "9,10" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 3 -ne "8,2,5,3,2" -u "11,12,13,14,15" -b $networkDataRate
    python3 computeDistanceToNE_mobility.py -n $numMobileDevice -k $numNetwork -dir "$rootDir/" -t 400 -r $numRun -pr 1 -p 3 -ne "8,2,5,3,2" -u "16,17,18,19,20" -b $networkDataRate
else
    python3 combineDistanceToNashEquilibrium.py -r $numRun -t $numTimeSlot -d "$rootDir/" -w $rollingAvgWindow
    python3 stability.py -d "$rootDir/" -r $numRun -t $numTimeSlot -n numMobileDevice -k $numNetwork -p $stableProbability -c $consecutiveStableSlot -ne $nashEquilibrium
fi
