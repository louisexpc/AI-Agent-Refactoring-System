FROM gradle:7.4.2-jdk17 AS build
USER root
WORKDIR /app
COPY . .
RUN gradle build --no-daemon --no-build-cache -x test

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
